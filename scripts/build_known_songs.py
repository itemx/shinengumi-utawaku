#!/usr/bin/env python3
"""從已解析資料建立/更新 known_songs.json 驗證資料庫。

掃描 data/songs/*.json，提取所有有歌手的曲目，
累積成 known_songs.json 供未來解析時驗證使用。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
SONGS_DIR = DATA_DIR / "songs"
OUTPUT = DATA_DIR / "known_songs.json"


def build():
    """掃描所有頻道資料，建立已知歌曲資料庫。"""
    song_counter: Counter = Counter()  # "title||artist" → count
    artist_set: set[str] = set()
    title_set: set[str] = set()

    for path in SONGS_DIR.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for video in data.get("videos", []):
            for song in video.get("songs", []):
                title = song.get("title", "").strip()
                artist = song.get("artist", "").strip()
                if title and artist:
                    key = f"{title}||{artist}"
                    song_counter[key] += 1
                    artist_set.add(artist)
                    title_set.add(title)

    # 整理輸出格式
    songs = []
    for key, count in song_counter.most_common():
        title, artist = key.split("||", 1)
        songs.append({
            "title": title,
            "artist": artist,
            "count": count,
        })

    result = {
        "totalEntries": len(songs),
        "uniqueTitles": len(title_set),
        "uniqueArtists": len(artist_set),
        "songs": songs,
        "artists": sorted(artist_set),
    }

    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"✓ known_songs.json: {len(songs)} 首歌, {len(artist_set)} 位歌手")
    return result


if __name__ == "__main__":
    build()
