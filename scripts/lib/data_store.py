"""JSON 資料讀寫與合併邏輯。

管理 data/channels.json 和 data/songs/{channelId}.json。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# 預設資料目錄
DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _songs_dir(data_dir: Path = DATA_DIR) -> Path:
    d = data_dir / "songs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _channel_path(channel_id: str, data_dir: Path = DATA_DIR) -> Path:
    return _songs_dir(data_dir) / f"{channel_id}.json"


def _channels_path(data_dir: Path = DATA_DIR) -> Path:
    return data_dir / "channels.json"


def read_channel_data(channel_id: str, data_dir: Path = DATA_DIR) -> dict | None:
    """讀取單一頻道的解析資料。"""
    path = _channel_path(channel_id, data_dir)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_channel_data(data: dict, data_dir: Path = DATA_DIR) -> None:
    """寫入頻道解析資料。"""
    channel_id = data["channelId"]
    path = _channel_path(channel_id, data_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def new_channel_data(channel_id: str, channel_name: str) -> dict:
    """建立空白頻道資料結構。"""
    return {
        "channelId": channel_id,
        "channelName": channel_name,
        "lastFetched": datetime.now(timezone.utc).isoformat(),
        "videos": [],
    }


def merge_video(channel_data: dict, video: dict) -> dict:
    """合併一部影片到頻道資料中。

    以 videoId 去重。若影片已存在，合併新的歌曲 (不覆蓋既有)。
    """
    existing_videos: list[dict] = channel_data.get("videos", [])
    video_id = video["videoId"]

    # 先對傳入的 songs 本身去重 (來源可能含日/英雙語清單等情況)
    incoming_songs: list[dict] = []
    seen_seconds: set[int] = set()
    for song in video.get("songs", []):
        if song["seconds"] in seen_seconds:
            continue
        seen_seconds.add(song["seconds"])
        incoming_songs.append(song)
    video["songs"] = incoming_songs

    # 查找已存在的影片
    for i, existing in enumerate(existing_videos):
        if existing["videoId"] == video_id:
            # title: 只要新值非空就覆蓋 (以最新為準，例如實況者改標題)
            if video.get("title"):
                existing["title"] = video["title"]
            # 其他欄位: 只在空白時補填
            for key in ("publishedAt", "type"):
                if not existing.get(key) and video.get(key):
                    existing[key] = video[key]
            # 合併歌曲: 以 seconds 去重
            existing_seconds = {s["seconds"] for s in existing.get("songs", [])}
            for song in incoming_songs:
                if song["seconds"] not in existing_seconds:
                    existing["songs"].append(song)
            existing_videos[i] = existing
            channel_data["videos"] = existing_videos
            channel_data["lastFetched"] = datetime.now(timezone.utc).isoformat()
            return channel_data

    # 新影片: 直接加入
    existing_videos.append(video)
    channel_data["videos"] = existing_videos
    channel_data["lastFetched"] = datetime.now(timezone.utc).isoformat()
    return channel_data


def get_existing_video_ids(channel_id: str, data_dir: Path = DATA_DIR) -> set[str]:
    """取得頻道已有的影片 ID 集合。"""
    data = read_channel_data(channel_id, data_dir)
    if data is None:
        return set()
    return {v["videoId"] for v in data.get("videos", [])}


# --- channels.json 管理 ---

def read_channels_registry(data_dir: Path = DATA_DIR) -> list[dict]:
    """讀取頻道註冊清單。"""
    path = _channels_path(data_dir)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_channels_registry(channels: list[dict], data_dir: Path = DATA_DIR) -> None:
    """寫入頻道註冊清單。"""
    path = _channels_path(data_dir)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)


def find_channel(channel_id: str, data_dir: Path = DATA_DIR) -> dict | None:
    """在 channels.json 中查找頻道。"""
    for ch in read_channels_registry(data_dir):
        if ch["channelId"] == channel_id:
            return ch
    return None


def upsert_channel(
    channel_id: str,
    name: str,
    data_dir: Path = DATA_DIR,
    **kwargs: Any,
) -> None:
    """新增或更新 channels.json 中的頻道。"""
    channels = read_channels_registry(data_dir)

    for ch in channels:
        if ch["channelId"] == channel_id:
            ch["name"] = name
            ch.update(kwargs)
            write_channels_registry(channels, data_dir)
            return

    # 新增
    entry: dict[str, Any] = {
        "channelId": channel_id,
        "name": name,
        "keywords": ["歌枠", "singing", "karaoke", "歌ってみた"],
    }
    entry.update(kwargs)
    channels.append(entry)
    write_channels_registry(channels, data_dir)
