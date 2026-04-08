"""YouTube URL / ID 解析器。

支援頻道、影片、播放清單的各種 URL 格式與裸 ID。
"""

from __future__ import annotations

import re
from typing import NamedTuple
from urllib.parse import urlparse, parse_qs


class UrlParseResult(NamedTuple):
    type: str  # 'channel' | 'video' | 'playlist'
    id: str


_VIDEO_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def parse(url_or_id: str) -> UrlParseResult:
    """解析 YouTube URL 或裸 ID。

    Args:
        url_or_id: YouTube URL 或裸 channel/video/playlist ID。

    Returns:
        UrlParseResult(type, id)

    Raises:
        ValueError: 無法辨識的格式。
    """
    text = url_or_id.strip()
    if not text:
        raise ValueError("空字串")

    # 嘗試作為 URL 解析
    parsed = urlparse(text)
    if parsed.scheme in ("http", "https"):
        return _parse_url(parsed)

    # 無 scheme — 可能是裸 ID 或 handle
    return _parse_bare(text)


def _parse_url(parsed) -> UrlParseResult:
    """解析完整 YouTube URL。"""
    host = (parsed.hostname or "").lower().replace("www.", "")
    path = parsed.path.rstrip("/")
    qs = parse_qs(parsed.query)

    if host not in ("youtube.com", "youtu.be", "m.youtube.com", "music.youtube.com"):
        raise ValueError(f"非 YouTube 網域: {host}")

    # youtu.be/{videoId}
    if host == "youtu.be":
        video_id = path.lstrip("/").split("/")[0]
        if _VIDEO_ID_RE.match(video_id):
            return UrlParseResult("video", video_id)
        raise ValueError(f"無效的 youtu.be 影片 ID: {video_id}")

    # /watch?v={videoId}
    if path == "/watch" and "v" in qs:
        video_id = qs["v"][0]
        if _VIDEO_ID_RE.match(video_id):
            return UrlParseResult("video", video_id)
        raise ValueError(f"無效的影片 ID: {video_id}")

    # /live/{videoId}
    if path.startswith("/live/"):
        video_id = path.split("/")[2]
        if _VIDEO_ID_RE.match(video_id):
            return UrlParseResult("video", video_id)
        raise ValueError(f"無效的 live 影片 ID: {video_id}")

    # /shorts/{videoId}
    if path.startswith("/shorts/"):
        video_id = path.split("/")[2]
        if _VIDEO_ID_RE.match(video_id):
            return UrlParseResult("video", video_id)
        raise ValueError(f"無效的 shorts 影片 ID: {video_id}")

    # /playlist?list={playlistId}
    if path == "/playlist" and "list" in qs:
        return UrlParseResult("playlist", qs["list"][0])

    # /channel/{channelId}
    if path.startswith("/channel/"):
        channel_id = path.split("/")[2]
        return UrlParseResult("channel", channel_id)

    # /@{handle}
    if path.startswith("/@"):
        handle = path.split("/")[1]  # includes @
        return UrlParseResult("channel", handle)

    # /c/{customName} — 舊版自訂 URL
    if path.startswith("/c/"):
        custom = path.split("/")[2]
        return UrlParseResult("channel", f"@{custom}")

    raise ValueError(f"無法辨識的 YouTube URL 路徑: {path}")


def _parse_bare(text: str) -> UrlParseResult:
    """解析裸 ID 或 handle。"""
    # @handle
    if text.startswith("@"):
        return UrlParseResult("channel", text)

    # UC 開頭, 24 字元 = channel ID
    if text.startswith("UC") and len(text) == 24:
        return UrlParseResult("channel", text)

    # PL 開頭 = playlist ID
    if text.startswith("PL"):
        return UrlParseResult("playlist", text)

    # UU 開頭 = uploads playlist (頻道上傳清單)
    if text.startswith("UU") and len(text) == 24:
        return UrlParseResult("playlist", text)

    # 11 字元英數底線連字號 = video ID
    if _VIDEO_ID_RE.match(text):
        return UrlParseResult("video", text)

    raise ValueError(f"無法辨識的 ID 格式: {text}")
