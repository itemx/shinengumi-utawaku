#!/usr/bin/env python3
"""定期掃描新歌枠。

掃描所有已註冊頻道最近 N 天的影片，
嘗試抓取 setlist，找不到的加入 missing 清單。

用法:
    python scripts/scan_new.py [--days 7]

設計為 GitHub Actions 排程使用 (每 3 天一次)。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from scripts.lib.youtube_api import YouTubeClient
from scripts.lib.comment_parser import parse_comment, pick_best_comment_with_owner
from scripts.lib.title_parser import parse_cover_title, parse_original_song
from scripts.lib.normalizer import load_aliases, normalize, load_known_songs, fill_missing_artist
from scripts.lib.data_store import (
    read_channel_data,
    write_channel_data,
    new_channel_data,
    merge_video,
    get_existing_video_ids,
    find_channel,
    DATA_DIR,
)

MISSING_DIR = DATA_DIR / "missing"

# 歌枠判定 (同 find_missing.py)
_UTAWAKU_PATTERNS = re.compile(
    r"歌枠|karaoke|singing\s*stream|SINGING\s*STREAM",
    re.IGNORECASE,
)
_EXCLUDE_PATTERNS = re.compile(
    r"#shorts|歌ってみた|cover\b",
    re.IGNORECASE,
)


def load_missing(channel_id: str) -> dict:
    """載入既有 missing 資料。"""
    path = MISSING_DIR / f"{channel_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "channelId": channel_id,
        "channelName": "",
        "generatedAt": "",
        "totalSearched": 0,
        "totalWithSetlist": 0,
        "totalMissing": 0,
        "missing": [],
    }


def save_missing(channel_id: str, data: dict):
    """儲存 missing 資料。"""
    MISSING_DIR.mkdir(parents=True, exist_ok=True)
    path = MISSING_DIR / f"{channel_id}.json"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="掃描新歌枠")
    parser.add_argument(
        "--days", type=int, default=7,
        help="掃描最近幾天的影片 (預設 7)",
    )
    args = parser.parse_args()

    yt = YouTubeClient()
    aliases = load_aliases(DATA_DIR / "aliases.json")
    known = load_known_songs(DATA_DIR / "known_songs.json")

    # 計算時間範圍
    since = datetime.now(timezone.utc) - timedelta(days=args.days)
    published_after = since.strftime("%Y-%m-%dT00:00:00Z")
    print(f"📅 掃描 {args.days} 天內的新影片 (since {published_after})")

    # 讀取所有已註冊頻道
    channels_path = DATA_DIR / "channels.json"
    with open(channels_path, encoding="utf-8") as f:
        channels = json.load(f)

    total_new = 0
    total_missing = 0

    for ch in channels:
        channel_id = ch["channelId"]
        channel_name = ch["name"]
        keywords = ch.get("keywords")
        print(f"\n📺 {channel_name} ({channel_id})")

        # 搜尋最近的歌枠
        try:
            vid_ids = yt.search_singing_streams(
                channel_id, keywords, published_after=published_after,
            )
        except Exception as e:
            print(f"   ⚠ 搜尋失敗: {e}")
            continue

        if not vid_ids:
            print(f"   ✓ 無新影片")
            continue

        print(f"   找到 {len(vid_ids)} 部影片")

        # 過濾已存在的 (有 songs 的)
        existing = get_existing_video_ids(channel_id)
        ch_data_raw = read_channel_data(channel_id)
        existing_with_songs = set()
        if ch_data_raw:
            existing_with_songs = {
                v["videoId"] for v in ch_data_raw.get("videos", [])
                if v.get("songs")
            }

        vid_ids = [v for v in vid_ids if v not in existing_with_songs]
        if not vid_ids:
            print(f"   ✓ 全部已有セトリ")
            continue

        print(f"   待處理: {len(vid_ids)} 部")

        # 載入頻道資料
        ch_data = ch_data_raw or new_channel_data(channel_id, channel_name)

        # 載入 missing 資料
        missing_data = load_missing(channel_id)
        missing_data["channelName"] = channel_name
        existing_missing_ids = {m["videoId"] for m in missing_data.get("missing", [])}

        for vid_id in vid_ids:
            try:
                vid_info = yt.get_video_info(vid_id)
                title = vid_info["title"]

                # 跳過排定中/直播中
                if vid_info.get("isUpcoming") or vid_info.get("isLive"):
                    print(f"      ⏳ {title[:50]}: 排定中/直播中")
                    continue

                # Cover / Original
                cover = parse_cover_title(title)
                if cover:
                    nr = normalize(cover.title, cover.artist, aliases)
                    artist = fill_missing_artist(nr.title, nr.artist, known)
                    vid_type = "short" if vid_info.get("isShort", cover.is_short) else "cover"
                    video_entry = {
                        "videoId": vid_id,
                        "title": title,
                        "publishedAt": vid_info["publishedAt"],
                        "songs": [{
                            "timestamp": "0:00", "seconds": 0,
                            "title": nr.title, "titleRaw": cover.title,
                            "artist": artist, "artistRaw": cover.artist,
                            "url": f"https://youtu.be/{vid_id}",
                        }],
                        "sourceCommentId": "",
                        "type": vid_type,
                    }
                    merge_video(ch_data, video_entry)
                    total_new += 1
                    print(f"      🎵 {nr.title} / {artist} [{vid_type}]")
                    continue

                original = parse_original_song(
                    title, vid_info.get("description", ""), vid_info.get("duration", ""),
                )
                if original:
                    nr = normalize(original.title, original.artist, aliases)
                    vid_type = "short" if vid_info.get("isShort", original.is_short) else "original"
                    video_entry = {
                        "videoId": vid_id,
                        "title": title,
                        "publishedAt": vid_info["publishedAt"],
                        "songs": [{
                            "timestamp": "0:00", "seconds": 0,
                            "title": nr.title, "titleRaw": original.title,
                            "artist": nr.artist or channel_name,
                            "artistRaw": original.artist or channel_name,
                            "url": f"https://youtu.be/{vid_id}",
                        }],
                        "sourceCommentId": "",
                        "type": vid_type,
                    }
                    merge_video(ch_data, video_entry)
                    total_new += 1
                    print(f"      🌟 {nr.title} [{vid_type}]")
                    continue

                # Stream: 嘗試抓 setlist
                comments = yt.get_comments(vid_id)
                songs = pick_best_comment_with_owner(comments, channel_id)

                if songs is None and vid_info.get("description"):
                    songs = parse_comment(vid_info["description"])

                if songs:
                    # 有 setlist
                    song_entries = []
                    for s in songs:
                        nr = normalize(s.title_raw, s.artist_raw, aliases)
                        artist = fill_missing_artist(nr.title, nr.artist, known)
                        song_entries.append({
                            "timestamp": s.timestamp, "seconds": s.seconds,
                            "title": nr.title, "titleRaw": s.title_raw,
                            "artist": artist, "artistRaw": s.artist_raw,
                            "url": f"https://youtu.be/{vid_id}?t={s.seconds}",
                        })
                    video_entry = {
                        "videoId": vid_id,
                        "title": title,
                        "publishedAt": vid_info["publishedAt"],
                        "songs": song_entries,
                        "sourceCommentId": "",
                        "type": "stream",
                    }
                    merge_video(ch_data, video_entry)
                    total_new += 1
                    print(f"      ✓ {title[:50]}: {len(song_entries)} 曲")
                else:
                    # 判斷是否為真歌枠
                    is_utawaku = bool(_UTAWAKU_PATTERNS.search(title))
                    is_excluded = bool(_EXCLUDE_PATTERNS.search(title))

                    if is_utawaku and not is_excluded:
                        # 加入 missing (或 refresh 既有項目的 title/publishedAt)
                        if vid_id not in existing_missing_ids:
                            missing_data["missing"].append({
                                "videoId": vid_id,
                                "title": title,
                                "publishedAt": vid_info["publishedAt"],
                                "url": f"https://www.youtube.com/watch?v={vid_id}",
                            })
                            existing_missing_ids.add(vid_id)
                            total_missing += 1
                            print(f"      📋 {title[:50]}: 加入 missing")
                        else:
                            # 已存在: 若標題或日期有變更則更新 (實況者可能改過)
                            for m in missing_data["missing"]:
                                if m["videoId"] == vid_id:
                                    if (m.get("title") != title
                                            or m.get("publishedAt") != vid_info["publishedAt"]):
                                        m["title"] = title
                                        m["publishedAt"] = vid_info["publishedAt"]
                                        print(f"      🔄 {title[:50]}: 更新 missing 資料")
                                    else:
                                        print(f"      📋 {title[:50]}: 已在 missing")
                                    break
                    else:
                        # 非歌枠，建立空記錄以避免重複掃描
                        if vid_id not in existing:
                            video_entry = {
                                "videoId": vid_id,
                                "title": title,
                                "publishedAt": vid_info["publishedAt"],
                                "songs": [],
                                "sourceCommentId": "",
                                "type": "stream",
                            }
                            merge_video(ch_data, video_entry)
                        print(f"      ⏭ {title[:50]}: 非歌枠，跳過")

            except Exception as e:
                print(f"      ⚠ {vid_id}: {e}")

        # 寫入
        write_channel_data(ch_data)

        # 更新 missing
        missing_data["generatedAt"] = datetime.now(timezone.utc).isoformat()
        missing_data["totalMissing"] = len(missing_data.get("missing", []))
        save_missing(channel_id, missing_data)

    # 摘要
    print(f"\n{'='*50}")
    print(f"完成！新增 {total_new} 部有セトリ影片, {total_missing} 部加入 missing")
    print(f"YouTube API 用量: {yt.units_consumed} units")


if __name__ == "__main__":
    main()
