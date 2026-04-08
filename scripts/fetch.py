#!/usr/bin/env python3
"""VTuber 歌枠セトリ擷取 CLI。

用法:
    python scripts/fetch.py <URL|ID> [...URL|ID] [--force]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 讓 scripts/lib 可被 import
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from scripts.lib.url_parser import parse as parse_url
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
    upsert_channel,
    find_channel,
    DATA_DIR,
)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(description="VTuber 歌枠セトリ擷取")
    parser.add_argument("urls", nargs="+", help="YouTube URL 或 ID (可多個)")
    parser.add_argument("--force", action="store_true", help="強制重新抓取已存在的影片")
    args = parser.parse_args()

    yt = YouTubeClient()
    aliases = load_aliases(DATA_DIR / "aliases.json")
    known = load_known_songs(DATA_DIR / "known_songs.json")

    # 1. 分類輸入
    channels: list[str] = []
    videos: list[str] = []
    playlists: list[str] = []

    for url in args.urls:
        try:
            result = parse_url(url)
        except ValueError as e:
            print(f"⚠ 跳過無法辨識的輸入: {url} ({e})")
            continue

        if result.type == "channel":
            channels.append(result.id)
        elif result.type == "video":
            videos.append(result.id)
        elif result.type == "playlist":
            playlists.append(result.id)

    # 2. 展開 playlists → videos
    for pl_id in playlists:
        print(f"📋 展開播放清單: {pl_id}")
        try:
            pl_videos = yt.get_playlist_items(pl_id)
            print(f"   找到 {len(pl_videos)} 部影片")
            videos.extend(pl_videos)
        except Exception as e:
            print(f"   ⚠ 失敗: {e}")

    # 3. 處理頻道
    channel_video_map: dict[str, list[str]] = {}  # channelId → [videoId]

    for ch_input in channels:
        try:
            # 解析 handle → channelId
            if ch_input.startswith("@"):
                print(f"🔍 解析 handle: {ch_input}")
                channel_id = yt.resolve_handle(ch_input)
            else:
                channel_id = ch_input

            # 取得頻道資訊並註冊
            info = yt.get_channel_info(channel_id)
            upsert_channel(channel_id, info["name"], avatar=info.get("avatar", ""))
            print(f"📺 頻道: {info['name']} ({channel_id})")

            # 搜尋歌枠
            ch_config = find_channel(channel_id)
            keywords = ch_config.get("keywords") if ch_config else None
            ch_videos = yt.search_singing_streams(channel_id, keywords)
            print(f"   找到 {len(ch_videos)} 部歌枠影片")
            channel_video_map[channel_id] = ch_videos

        except Exception as e:
            print(f"   ⚠ 頻道處理失敗: {e}")

    # 4. 處理單獨影片 (需先取得 channelId)
    for vid_id in videos:
        try:
            info = yt.get_video_info(vid_id)
            channel_id = info["channelId"]
            if channel_id not in channel_video_map:
                channel_video_map[channel_id] = []
                # 註冊頻道
                ch_info = yt.get_channel_info(channel_id)
                upsert_channel(channel_id, ch_info["name"], avatar=ch_info.get("avatar", ""))
            channel_video_map[channel_id].append(vid_id)
        except Exception as e:
            print(f"   ⚠ 影片資訊取得失敗 ({vid_id}): {e}")

    # 5. 逐頻道處理影片
    total_new_videos = 0
    total_new_songs = 0

    for channel_id, vid_ids in channel_video_map.items():
        # 去重
        vid_ids = list(dict.fromkeys(vid_ids))

        # 過濾已抓取
        if not args.force:
            existing = get_existing_video_ids(channel_id)
            before = len(vid_ids)
            vid_ids = [v for v in vid_ids if v not in existing]
            skipped = before - len(vid_ids)
            if skipped:
                print(f"   ⏭ 跳過 {skipped} 部已抓取影片")

        if not vid_ids:
            print(f"   ✓ 無新影片需要處理")
            continue

        # 載入或建立頻道資料
        ch_data = read_channel_data(channel_id)
        if ch_data is None:
            ch_info = find_channel(channel_id)
            name = ch_info["name"] if ch_info else channel_id
            ch_data = new_channel_data(channel_id, name)

        print(f"   🎤 處理 {len(vid_ids)} 部影片...")

        for vid_id in vid_ids:
            try:
                # 取得影片資訊
                vid_info = yt.get_video_info(vid_id)

                # 跳過排定中/直播中的影片 (尚未結束)
                if vid_info.get("isUpcoming") or vid_info.get("isLive"):
                    print(f"      ⏳ {vid_info['title'][:50]}: 排定中/直播中，跳過")
                    continue

                # 先嘗試作為 cover (歌ってみた) 解析
                cover = parse_cover_title(vid_info["title"])
                if cover:
                    nr = normalize(cover.title, cover.artist, aliases)
                    artist = fill_missing_artist(nr.title, nr.artist, known)
                    song_entries = [{
                        "timestamp": "0:00",
                        "seconds": 0,
                        "title": nr.title,
                        "titleRaw": cover.title,
                        "artist": artist,
                        "artistRaw": cover.artist,
                        "url": f"https://youtu.be/{vid_id}",
                    }]
                    # 用 API duration 判斷 Short (≤60s)，比標題 hashtag 更可靠
                    vid_type = "short" if vid_info.get("isShort", cover.is_short) else "cover"
                    video_entry = {
                        "videoId": vid_id,
                        "title": vid_info["title"],
                        "publishedAt": vid_info["publishedAt"],
                        "songs": song_entries,
                        "sourceCommentId": "",
                        "type": vid_type,
                    }
                    merge_video(ch_data, video_entry)
                    total_new_videos += 1
                    total_new_songs += 1
                    type_tag = " [Short]" if cover.is_short else " [Cover]"
                    print(f"      🎵 {nr.title} / {artist}{type_tag}")
                    continue

                # 嘗試作為原創曲解析
                original = parse_original_song(vid_info["title"], vid_info.get("description", ""), vid_info.get("duration", ""))
                if original:
                    nr = normalize(original.title, original.artist, aliases)
                    song_entries = [{
                        "timestamp": "0:00",
                        "seconds": 0,
                        "title": nr.title,
                        "titleRaw": original.title,
                        "artist": nr.artist or ch_data.get("channelName", ""),
                        "artistRaw": original.artist or ch_data.get("channelName", ""),
                        "url": f"https://youtu.be/{vid_id}",
                    }]
                    vid_type = "short" if vid_info.get("isShort", original.is_short) else "original"
                    video_entry = {
                        "videoId": vid_id,
                        "title": vid_info["title"],
                        "publishedAt": vid_info["publishedAt"],
                        "songs": song_entries,
                        "sourceCommentId": "",
                        "type": vid_type,
                    }
                    merge_video(ch_data, video_entry)
                    total_new_videos += 1
                    total_new_songs += 1
                    print(f"      🌟 {nr.title} / {nr.artist or ch_data.get('channelName', '')} [Original]")
                    continue

                # 歌枠: 取得留言
                comments = yt.get_comments(vid_id)

                # 也嘗試從影片描述擷取 (fallback)
                songs = pick_best_comment_with_owner(comments, channel_id)

                if songs is None and vid_info.get("description"):
                    songs = parse_comment(vid_info["description"])

                if songs is None:
                    print(f"      ⚠ {vid_info['title']}: 找不到セトリ")
                    continue

                # 正規化
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
                        "url": f"https://youtu.be/{vid_id}?t={s.seconds}",
                    })

                video_entry = {
                    "videoId": vid_id,
                    "title": vid_info["title"],
                    "publishedAt": vid_info["publishedAt"],
                    "songs": song_entries,
                    "sourceCommentId": "",
                    "type": "stream",
                }

                merge_video(ch_data, video_entry)
                total_new_videos += 1
                total_new_songs += len(song_entries)
                print(f"      ✓ {vid_info['title']}: {len(song_entries)} 曲")

            except Exception as e:
                print(f"      ⚠ {vid_id}: {e}")

        # 寫入
        write_channel_data(ch_data)

    # 摘要
    print(f"\n{'='*50}")
    print(f"完成！新增 {total_new_videos} 部影片, {total_new_songs} 首歌")
    print(f"YouTube API 用量: {yt.units_consumed} units")


if __name__ == "__main__":
    main()
