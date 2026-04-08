#!/usr/bin/env python3
"""統計產生器。

讀取 data/songs/*.json，產生 data/_stats.json。
供 Astro 頁面在 build 時讀取。
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
SONGS_DIR = DATA_DIR / "songs"
OUTPUT = DATA_DIR / "_stats.json"


def build_channel_stats(data: dict) -> dict:
    """建立單一頻道的統計。"""
    videos = data.get("videos", [])
    song_counter: Counter = Counter()
    artist_counter: Counter = Counter()
    monthly: Counter = Counter()
    all_appearances: dict[str, list] = {}  # title → appearances

    for video in videos:
        published = video.get("publishedAt", "")[:7]  # YYYY-MM
        if published:
            monthly[published] += 1

        for song in video.get("songs", []):
            title = song.get("title", song.get("titleRaw", ""))
            artist = song.get("artist", song.get("artistRaw", ""))
            key = f"{title}||{artist}"

            song_counter[key] += 1
            if artist:
                artist_counter[artist] += 1

            if key not in all_appearances:
                all_appearances[key] = []
            all_appearances[key].append({
                "videoId": video["videoId"],
                "channelId": data["channelId"],
                "date": video.get("publishedAt", ""),
                "title": video.get("title", ""),
                "url": song.get("url", ""),
            })

    # Top songs
    top_songs = []
    for key, count in song_counter.most_common(50):
        title, artist = key.split("||", 1)
        appearances = all_appearances.get(key, [])
        dates = [a["date"] for a in appearances if a["date"]]
        top_songs.append({
            "title": title,
            "artist": artist,
            "count": count,
            "appearances": appearances,
            "firstSung": min(dates) if dates else "",
            "lastSung": max(dates) if dates else "",
        })

    # Top artists
    top_artists = [
        {"artist": a, "count": c}
        for a, c in artist_counter.most_common(30)
    ]

    # Monthly activity
    monthly_activity = [
        {"month": m, "count": c}
        for m, c in sorted(monthly.items())
    ]

    # Unique songs
    unique_songs = len(song_counter)
    total_songs = sum(song_counter.values())

    # Recent videos
    sorted_videos = sorted(
        videos, key=lambda v: v.get("publishedAt", ""), reverse=True
    )
    recent_videos = [
        {
            "videoId": v["videoId"],
            "title": v["title"],
            "publishedAt": v.get("publishedAt", ""),
            "songCount": len(v.get("songs", [])),
        }
        for v in sorted_videos[:10]
    ]

    # 分類計數
    streams = [v for v in videos if v.get("type", "stream") == "stream"]
    shorts = [v for v in videos if v.get("type") == "short"]
    covers = [v for v in videos if v.get("type") == "cover"]
    originals = [v for v in videos if v.get("type") == "original"]

    return {
        "channelId": data["channelId"],
        "channelName": data.get("channelName", ""),
        "uniqueSongs": unique_songs,
        "totalSongs": total_songs,
        "totalVideos": len(videos),
        "streamCount": len(streams),
        "shortCount": len(shorts),
        "coverCount": len(covers) + len(originals),
        "originalCount": len(originals),
        "topSongs": top_songs,
        "topArtists": top_artists,
        "monthlyActivity": monthly_activity,
        "recentVideos": recent_videos,
    }


def main():
    if not SONGS_DIR.exists():
        print("data/songs/ 不存在，產生空統計")
        OUTPUT.write_text("{}", encoding="utf-8")
        return

    channel_files = list(SONGS_DIR.glob("*.json"))
    if not channel_files:
        print("無頻道資料，產生空統計")
        OUTPUT.write_text("{}", encoding="utf-8")
        return

    stats: dict[str, dict] = {}

    for path in channel_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            channel_id = data.get("channelId", path.stem)
            stats[channel_id] = build_channel_stats(data)
            video_count = len(data.get("videos", []))
            song_count = stats[channel_id]["totalSongs"]
            print(f"  {data.get('channelName', channel_id)}: {video_count} 影片, {song_count} 曲")
        except Exception as e:
            print(f"  ⚠ {path.name}: {e}")

    OUTPUT.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n✓ 統計已寫入 {OUTPUT}")

    # 清理 missing: 移除已入庫的影片
    missing_dir = DATA_DIR / "missing"
    if missing_dir.exists():
        for mpath in missing_dir.glob("*.json"):
            try:
                channel_id = mpath.stem
                mdata = json.loads(mpath.read_text(encoding="utf-8"))
                # 取得該頻道已收錄的 videoId
                songs_path = SONGS_DIR / f"{channel_id}.json"
                existing_ids = set()
                if songs_path.exists():
                    ch_data = json.loads(songs_path.read_text(encoding="utf-8"))
                    existing_ids = {v["videoId"] for v in ch_data.get("videos", [])}

                before = len(mdata.get("missing", []))
                mdata["missing"] = [
                    m for m in mdata.get("missing", [])
                    if m["videoId"] not in existing_ids
                ]
                mdata["totalMissing"] = len(mdata["missing"])
                after = len(mdata["missing"])

                if before != after:
                    mpath.write_text(
                        json.dumps(mdata, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    print(f"  missing/{channel_id}: {before} → {after} (-{before - after})")
            except Exception as e:
                print(f"  ⚠ missing/{mpath.name}: {e}")


if __name__ == "__main__":
    main()
