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
from scripts.lib.url_parser import _VIDEO_ID_RE
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
    # 信任境界は「setlist-submission label を付けられる人」= collaborator だけ。
    # それでも frontmatter はレビュー対象外なので、ファイル名・属性に入る値だけ検証する
    issue = fetch_issue(issue_number)
    body = issue.get("body", "")
    print(f"  作者: {issue.get('user', {}).get('login', '')}")

    # 解析 frontmatter
    metadata, setlist_text = parse_frontmatter(body)
    video_id = metadata.get("video_id", "")
    video_title = metadata.get("video_title", "")

    if not _VIDEO_ID_RE.match(video_id):
        print(f"  ❌ video_id の形式が不正: {video_id!r}")
        sys.exit(1)

    print(f"  影片: {video_title} ({video_id})")

    # 解析セトリ
    # cover/original/short 為單曲投稿: 允許 1 首、保留 0:00
    vid_type = metadata.get("type", "stream")
    if vid_type not in ("stream", "cover", "original", "short"):
        print(f"  ❌ type が不正: {vid_type!r}")
        sys.exit(1)
    if vid_type in ("cover", "original", "short"):
        min_songs = 1
        songs = parse_comment(setlist_text, min_songs=1, skip_zero=False, filter_chatter=False)
    else:
        # 3 曲の下限は「たまたま時間が書かれただけのコメント」を setlist と誤認しない
        # ための保険。投稿ページから来たもの (source: manual) は人が見て出しているので
        # 下限は要らない ——「歌雑で 2 曲だけ」のような配信が弾かれていた。
        min_songs = 1 if metadata.get("source") == "manual" else 3
        songs = parse_comment(setlist_text, min_songs=min_songs)
    if songs is None:
        found = parse_comment(setlist_text, min_songs=1, filter_chatter=False) or []
        print(
            f"  ❌ 無法解析セトリ: 取得 {len(found)} 曲、需要至少 {min_songs} 曲。"
            "請確認每行格式為「時間 曲名 / 歌手」，時間後面要有半形空白。"
        )
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
    # channel_id はそのまま data/songs/{id}.json のファイル名になる。
    # 登録済みの ID 以外は受けない（../channels 等でほかのファイルを潰されないように）
    if channel_id and channel_id not in {c["channelId"] for c in channels}:
        print(f"  ❌ 未登録の channel_id: {channel_id!r}")
        sys.exit(1)

    if not channel_id and len(channels) == 1:
        channel_id = channels[0]["channelId"]

    # Fallback: 從影片標題比對頻道名稱
    if not channel_id:
        title_lower = video_title.lower()
        for ch in channels:
            ch_name = ch.get("name", "")
            # 嘗試匹配頻道名稱中的日文部分 (例: "渉海よひら" from "Yohira ch. 渉海よひら")
            parts = ch_name.split()
            for part in parts:
                if len(part) >= 3 and part.lower() in title_lower:
                    channel_id = ch["channelId"]
                    print(f"  ℹ 從影片標題比對到頻道: {ch_name}")
                    break
            if channel_id:
                break

    if not channel_id:
        print("  ❌ 無法判斷頻道")
        sys.exit(1)

    # 載入或建立頻道資料
    ch_data = read_channel_data(channel_id)
    if ch_data is None:
        ch_info = find_channel(channel_id)
        name = ch_info["name"] if ch_info else channel_id
        ch_data = new_channel_data(channel_id, name)

    # 重複偵測
    existing_ids = {v["videoId"] for v in ch_data.get("videos", [])}
    if video_id in existing_ids:
        existing_video = next(v for v in ch_data["videos"] if v["videoId"] == video_id)
        existing_songs = len(existing_video.get("songs", []))
        print(f"  ⚠ 此影片已收錄 ({existing_songs} 曲)")

    # 取得影片發布日期
    published_at = ""
    yt_api_key = os.environ.get("YOUTUBE_API_KEY", "")
    if yt_api_key:
        try:
            from scripts.lib.youtube_api import YouTubeClient
            yt = YouTubeClient(yt_api_key)
            info = yt.get_video_info(video_id)
            published_at = info.get("publishedAt", "")
            print(f"  📅 發布日期: {published_at}")
        except Exception as e:
            print(f"  ⚠ 無法取得發布日期: {e}")

    # 建立 video entry
    video_entry = {
        "videoId": video_id,
        "title": video_title,
        "publishedAt": published_at,
        "songs": song_entries,
        "sourceCommentId": f"issue#{issue_number}",
        "type": vid_type,
    }

    merge_video(ch_data, video_entry)
    write_channel_data(ch_data)

    print(f"  ✓ 已寫入 {channel_id}.json: {len(song_entries)} 曲")

    unmatched = [s["title"] for s in song_entries if not s["artist"]]
    if unmatched:
        print(f"  ⚠ 歌手未匹配 {len(unmatched)} 曲: " + "、".join(unmatched))


if __name__ == "__main__":
    main()
