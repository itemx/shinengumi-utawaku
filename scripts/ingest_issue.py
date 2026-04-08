#!/usr/bin/env python3
"""從 GitHub Issue 解析セトリ並寫入資料。

用法 (由 GitHub Action 呼叫):
    python scripts/ingest_issue.py <issue_number>

環境變數:
    GITHUB_TOKEN: GitHub API token
    GITHUB_REPOSITORY: owner/repo (由 Action 自動設定)
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

from scripts.lib.comment_parser import parse_comment
from scripts.lib.normalizer import load_aliases, normalize, load_known_songs, fill_missing_artist
from scripts.lib.data_store import (
    read_channel_data,
    write_channel_data,
    new_channel_data,
    merge_video,
    find_channel,
    DATA_DIR,
)


def fetch_issue(issue_number: int) -> dict:
    """從 GitHub API 取得 Issue 內容。"""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")

    url = f"https://api.github.com/repos/{repo}/issues/{issue_number}"
    headers = {"Authorization": f"token {token}"} if token else {}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_frontmatter(body: str) -> tuple[dict, str]:
    """解析 Issue body 的 frontmatter (--- 區塊) 和セトリ文字。

    Returns:
        (metadata_dict, setlist_text)
    """
    parts = body.split("---", 2)
    if len(parts) < 3:
        return {}, body

    fm_text = parts[1].strip()
    setlist_text = parts[2].strip()

    metadata: dict = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if ":" in line:
            key, val = line.split(":", 1)
            metadata[key.strip()] = val.strip()

    return metadata, setlist_text


def main():
    if len(sys.argv) < 2:
        print("用法: python scripts/ingest_issue.py <issue_number>")
        sys.exit(1)

    issue_number = int(sys.argv[1])
    print(f"處理 Issue #{issue_number}")

    # 取得 Issue
    issue = fetch_issue(issue_number)
    body = issue.get("body", "")
    author = issue.get("user", {}).get("login", "")
    print(f"  作者: {author}")

    # 安全檢查: 允許清單
    allowed_users_str = os.environ.get("ALLOWED_USERS", "")
    allowed_users = [u.strip() for u in allowed_users_str.split(",") if u.strip()]

    if allowed_users and author not in allowed_users:
        print(f"  ⚠ 作者 {author} 不在允許清單中，需手動加 approved label")
        # 檢查是否有 approved label
        labels = [l["name"] for l in issue.get("labels", [])]
        if "approved" not in labels:
            print("  ❌ 未經批准，跳過")
            sys.exit(0)
        print("  ✓ 已有 approved label，繼續處理")

    # 解析 frontmatter
    metadata, setlist_text = parse_frontmatter(body)
    video_id = metadata.get("video_id", "")
    video_title = metadata.get("video_title", "")

    if not video_id:
        print("  ❌ 找不到 video_id")
        sys.exit(1)

    print(f"  影片: {video_title} ({video_id})")

    # 解析セトリ
    songs = parse_comment(setlist_text)
    if songs is None:
        print("  ❌ 無法解析セトリ")
        sys.exit(1)

    print(f"  解析: {len(songs)} 曲")

    # 正規化
    aliases = load_aliases(DATA_DIR / "aliases.json")
    known = load_known_songs(DATA_DIR / "known_songs.json")

    song_entries = []
    for s in songs:
        nr = normalize(s.title_raw, s.artist_raw, aliases)
        artist = fill_missing_artist(nr.title, nr.artist, known)
        song_entries.append({
            "timestamp": s.timestamp,
            "seconds": s.seconds,
            "title": nr.title,
            "titleRaw": s.title_raw,
            "artist": artist,
            "artistRaw": s.artist_raw,
            "url": f"https://youtu.be/{video_id}?t={s.seconds}",
        })

    # 從 video_id 推斷 channel (需要已在 channels.json 中)
    # 嘗試所有已註冊頻道
    channels = json.loads((DATA_DIR / "channels.json").read_text(encoding="utf-8"))
    channel_id = metadata.get("channel_id", "")

    if not channel_id and len(channels) == 1:
        channel_id = channels[0]["channelId"]

    if not channel_id:
        print("  ❌ 無法判斷頻道")
        sys.exit(1)

    # 載入或建立頻道資料
    ch_data = read_channel_data(channel_id)
    if ch_data is None:
        ch_info = find_channel(channel_id)
        name = ch_info["name"] if ch_info else channel_id
        ch_data = new_channel_data(channel_id, name)

    # 建立 video entry
    video_entry = {
        "videoId": video_id,
        "title": video_title,
        "publishedAt": "",  # Issue 不一定有日期
        "songs": song_entries,
        "sourceCommentId": f"issue#{issue_number}",
        "type": "stream",
    }

    merge_video(ch_data, video_entry)
    write_channel_data(ch_data)

    print(f"  ✓ 已寫入 {channel_id}.json: {len(song_entries)} 曲")

    # 記錄未匹配的曲名
    unmatched = [s for s in song_entries if not s["artist"]]
    if unmatched:
        log_path = DATA_DIR / "unmatched.log"
        with open(log_path, "a", encoding="utf-8") as f:
            for s in unmatched:
                f.write(f"[issue#{issue_number}] {s['title']}\n")
        print(f"  ⚠ {len(unmatched)} 曲未匹配歌手 → unmatched.log")


if __name__ == "__main__":
    main()
