"""YouTube Data API v3 封裝。

提供頻道、影片、留言、播放清單的查詢方法。
"""

from __future__ import annotations

import os
import re
from googleapiclient.discovery import build


def _is_short_duration(duration_iso: str) -> bool:
    """判斷 ISO 8601 duration 是否 ≤ 60 秒 (Short)。

    Examples: "PT45S" → True, "PT1M30S" → False, "PT1H" → False
    """
    if not duration_iso:
        return False
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_iso)
    if not m:
        return False
    hours = int(m.group(1) or 0)
    minutes = int(m.group(2) or 0)
    seconds = int(m.group(3) or 0)
    total = hours * 3600 + minutes * 60 + seconds
    return total <= 60


class YouTubeClient:
    """YouTube Data API v3 用戶端。"""

    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("YOUTUBE_API_KEY", "")
        if not key:
            raise ValueError("未設定 YOUTUBE_API_KEY")
        self._service = build("youtube", "v3", developerKey=key)
        self._units = 0

    @property
    def units_consumed(self) -> int:
        return self._units

    def resolve_handle(self, handle: str) -> str:
        """@handle → channelId (1 unit)。"""
        clean = handle.lstrip("@")
        resp = self._service.channels().list(
            part="id", forHandle=clean, maxResults=1
        ).execute()
        self._units += 1
        items = resp.get("items", [])
        if not items:
            raise ValueError(f"找不到頻道: @{clean}")
        return items[0]["id"]

    def get_channel_info(self, channel_id: str) -> dict:
        """取得頻道名稱與縮圖 (1 unit)。"""
        resp = self._service.channels().list(
            part="snippet", id=channel_id
        ).execute()
        self._units += 1
        items = resp.get("items", [])
        if not items:
            raise ValueError(f"找不到頻道: {channel_id}")
        snippet = items[0]["snippet"]
        return {
            "channelId": channel_id,
            "name": snippet.get("title", ""),
            "avatar": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
        }

    def get_video_info(self, video_id: str) -> dict:
        """取得影片 metadata (1 unit)。含 duration 和直播狀態。"""
        resp = self._service.videos().list(
            part="snippet,contentDetails,liveStreamingDetails", id=video_id
        ).execute()
        self._units += 1
        items = resp.get("items", [])
        if not items:
            raise ValueError(f"找不到影片: {video_id}")
        snippet = items[0]["snippet"]
        content = items[0].get("contentDetails", {})
        live = items[0].get("liveStreamingDetails", {})
        duration_iso = content.get("duration", "")  # e.g. "PT1M30S", "PT45S"
        broadcast = snippet.get("liveBroadcastContent", "none")  # "upcoming", "live", "none"
        return {
            "videoId": video_id,
            "channelId": snippet.get("channelId", ""),
            "title": snippet.get("title", ""),
            "publishedAt": snippet.get("publishedAt", ""),
            "description": snippet.get("description", ""),
            "duration": duration_iso,
            "isShort": _is_short_duration(duration_iso),
            "isUpcoming": broadcast == "upcoming",
            "isLive": broadcast == "live",
        }

    def search_singing_streams(
        self, channel_id: str, keywords: list[str] | None = None,
        published_after: str | None = None,
    ) -> list[str]:
        """搜尋頻道的歌枠影片 (100 units/page)。

        Args:
            channel_id: YouTube 頻道 ID。
            keywords: 搜尋關鍵字。
            published_after: ISO 8601 日期 (e.g. "2026-04-01T00:00:00Z")，
                只搜此日期之後的影片。

        Returns:
            videoId 列表。
        """
        if keywords is None:
            keywords = ["歌枠", "singing", "karaoke", "歌ってみた"]

        query = " | ".join(keywords)
        video_ids: list[str] = []
        page_token = None

        while True:
            params = dict(
                part="id",
                channelId=channel_id,
                q=query,
                type="video",
                maxResults=50,
                order="date",
                pageToken=page_token,
            )
            if published_after:
                params["publishedAfter"] = published_after
            resp = self._service.search().list(**params).execute()
            self._units += 100

            for item in resp.get("items", []):
                vid = item.get("id", {}).get("videoId")
                if vid:
                    video_ids.append(vid)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return video_ids

    def get_playlist_items(self, playlist_id: str) -> list[str]:
        """取得播放清單內所有影片 (1 unit/page)。"""
        video_ids: list[str] = []
        page_token = None

        while True:
            resp = self._service.playlistItems().list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=page_token,
            ).execute()
            self._units += 1

            for item in resp.get("items", []):
                vid = item.get("contentDetails", {}).get("videoId")
                if vid:
                    video_ids.append(vid)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break

        return video_ids

    def get_comments(self, video_id: str, max_results: int = 100) -> list[dict]:
        """取得影片留言 (1 unit/page)。

        Returns:
            commentThread 原始資料列表。
        """
        comments: list[dict] = []
        page_token = None
        fetched = 0

        while fetched < max_results:
            per_page = min(100, max_results - fetched)
            try:
                resp = self._service.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=per_page,
                    order="relevance",
                    pageToken=page_token,
                ).execute()
            except Exception:
                # 留言區關閉或無法存取
                break
            self._units += 1

            items = resp.get("items", [])
            comments.extend(items)
            fetched += len(items)

            page_token = resp.get("nextPageToken")
            if not page_token or not items:
                break

        return comments
