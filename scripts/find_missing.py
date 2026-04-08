#!/usr/bin/env python3
"""找出「是歌枠但沒有セトリ」的直播。

掃描頻道搜到的歌枠影片，比對已解析資料，
列出缺少 timestamp 的影片供手動補充。

用法:
    python scripts/find_missing.py <URL|ID>

輸出:
    data/missing_setlists.json
    stdout 表格
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from scripts.lib.url_parser import parse as parse_url
from scripts.lib.youtube_api import YouTubeClient
from scripts.lib.data_store import (
    get_existing_video_ids,
    find_channel,
    DATA_DIR,
)

# 歌枠標題特徵 (用來區分真歌枠 vs shorts/歌ってみた)
_UTAWAKU_PATTERNS = re.compile(
    r"歌枠|karaoke|singing\s*stream|SINGING\s*STREAM",
    re.IGNORECASE,
)

# 非歌枠的排除模式
_EXCLUDE_PATTERNS = re.compile(
    r"#shorts|歌ってみた|cover\b",
    re.IGNORECASE,
)

MISSING_DIR = DATA_DIR / "missing"


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="找出缺少セトリ的歌枠")
    parser.add_argument("url", help="YouTube 頻道 URL 或 ID")
    args = parser.parse_args()

    result = parse_url(args.url)
    if result.type != "channel":
        print("請提供頻道 URL 或 ID")
        return

    yt = YouTubeClient()

    # 解析 handle
    if result.id.startswith("@"):
        channel_id = yt.resolve_handle(result.id)
    else:
        channel_id = result.id

    ch_info = yt.get_channel_info(channel_id)
    print(f"📺 {ch_info['name']} ({channel_id})")

    # 搜尋歌枠
    ch_config = find_channel(channel_id)
    keywords = ch_config.get("keywords") if ch_config else None
    all_videos = yt.search_singing_streams(channel_id, keywords)
    print(f"   搜到 {len(all_videos)} 部影片")

    # 已有セトリ的影片
    existing = get_existing_video_ids(channel_id)
    print(f"   已有セトリ: {len(existing)} 部")

    # 找出缺少的
    missing_ids = [v for v in all_videos if v not in existing]
    print(f"   待檢查: {len(missing_ids)} 部")

    # 取得影片資訊，判斷是否為真歌枠
    missing_utawaku = []

    for vid_id in missing_ids:
        try:
            info = yt.get_video_info(vid_id)
            title = info["title"]

            # 判斷是否為真歌枠 (排除 shorts/歌ってみた)
            is_utawaku = bool(_UTAWAKU_PATTERNS.search(title))
            is_excluded = bool(_EXCLUDE_PATTERNS.search(title))

            if is_utawaku and not is_excluded:
                entry = {
                    "videoId": vid_id,
                    "title": title,
                    "publishedAt": info["publishedAt"],
                    "url": f"https://www.youtube.com/watch?v={vid_id}",
                }
                missing_utawaku.append(entry)

        except Exception as e:
            print(f"   ⚠ {vid_id}: {e}")

    # 按日期排序 (新→舊)
    missing_utawaku.sort(key=lambda x: x["publishedAt"], reverse=True)

    # 輸出
    print(f"\n{'='*60}")
    print(f"歌枠但沒セトリ: {len(missing_utawaku)} 部 (需手動補 timestamp)")
    print(f"{'='*60}")

    for i, entry in enumerate(missing_utawaku, 1):
        date = entry["publishedAt"][:10]
        title_short = entry["title"][:55]
        print(f"  {i:2d}. [{date}] {title_short}")
        print(f"      {entry['url']}")

    # 存檔
    output_data = {
        "channelId": channel_id,
        "channelName": ch_info["name"],
        "generatedAt": __import__("datetime").datetime.now().isoformat(),
        "totalSearched": len(all_videos),
        "totalWithSetlist": len(existing),
        "totalMissing": len(missing_utawaku),
        "missing": missing_utawaku,
    }

    MISSING_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MISSING_DIR / f"{channel_id}.json"
    out_path.write_text(
        json.dumps(output_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✓ 已存入 {out_path}")
    print(f"  API 用量: {yt.units_consumed} units")


if __name__ == "__main__":
    main()
