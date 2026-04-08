"""留言 / セトリ文字解析器。

從 YouTube 留言中擷取含 timestamp 的歌曲列表。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SongEntry:
    timestamp: str      # 原始格式 "1:03:25" or "03:25"
    seconds: int        # 換算秒數
    title_raw: str      # 原始解析曲名
    artist_raw: str     # 原始解析歌手名


# Timestamp 行正則: 開頭可選空白 + timestamp + 空白 + 剩餘文字
_TIMESTAMP_LINE_RE = re.compile(
    r"^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$", re.MULTILINE
)

# 帶結束時間的格式: "00:02:30 - 00:06:47 01. sweet timer - iLiFE!"
_RANGE_TIMESTAMP_RE = re.compile(
    r"^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*-\s*\d{1,2}:\d{2}(?::\d{2})?\s+(.+)$",
    re.MULTILINE,
)

# 編號前綴: "01. " "1. " "01 " 等
_NUMBERING_RE = re.compile(r"^\d{1,3}[\.\)]\s*")

# 用於清理裝飾符號
_DECORATION_RE = re.compile(r"[🎵🎶🎤🎸🎹🎼🎧♪♫★☆✦✧●◉◆◇▶►▸▹⏰🔴💜❤️🩵🩷💛💚🧡🤍🖤💙]+")
_HASHTAG_LINE_RE = re.compile(r"^\s*#\S+", re.MULTILINE)

# 曲名/歌手分隔符 (依優先序)
_SEPARATORS = [" / ", " ／ ", " - ", " − ", " ー "]

# 非歌曲的 timestamp 項目 (配信標記)
_SKIP_TITLES = {
    "スタート", "start", "START", "エンディング", "ending", "ENDING",
    "ED", "OP", "オープニング", "opening", "雑談", "トーク",
    "休憩", "break", "開始", "終了", "配信開始", "配信終了",
    "おまけ", "アンコール前MC",
    "オープニングトーク", "エンディングトーク", "MC",
    "はじまり", "始まり",
}

# 雜談 timestamp 特徵 (含「話」「の件」等)
_TALK_PATTERNS = re.compile(
    r"(?:の話$|の件|トーク|について|という話|タンク|変更|買おう|休みたい|リアクション|募集|告知|発表|思い出$|ミス)",
)


def _is_likely_song(title: str, has_artist: bool = True) -> bool:
    """判斷 timestamp 項目是否為歌曲（非雜談/配信標記）。

    Args:
        title: 解析出的標題。
        has_artist: 是否有 artist 分隔符。無歌手時判定更嚴格。
    """
    stripped = title.strip()
    # 完全符合跳過清單
    if stripped in _SKIP_TITLES:
        return False
    # 含雜談關鍵字
    if _TALK_PATTERNS.search(stripped):
        return False

    if has_artist:
        # 有歌手的情況: 寬鬆判定 (只排除超長標題)
        if len(stripped) > 50:
            return False
    else:
        # 無歌手的情況: 嚴格判定
        # 超過 20 字的無歌手項目很可能是雜談描述
        if len(stripped) > 20:
            return False
        # 包含句讀符號通常是雜談 (如「ありがとうねー!」「本当に...?」)
        if re.search(r"[、。！？…!?]", stripped):
            return False
        # 含平假名句子 (非曲名常見模式)
        hiragana_count = len(re.findall(r"[\u3040-\u309F]", stripped))
        if hiragana_count > len(stripped) * 0.6 and len(stripped) > 8:
            return False

    return True


def timestamp_to_seconds(ts: str) -> int:
    """將 timestamp 字串轉換為秒數。

    >>> timestamp_to_seconds("1:03:25")
    3805
    >>> timestamp_to_seconds("03:25")
    205
    """
    parts = ts.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    elif len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return 0


_PREFIX_RE = re.compile(
    r"^(?:アンコール|encore|Encore|EN)[：:\s]+\s*", re.IGNORECASE
)


def _split_title_artist(text: str) -> tuple[str, str]:
    """嘗試分離曲名與歌手。

    依序嘗試分隔符，若找到則分離，否則 artist 為空。
    也處理「」括號格式和各種變體分隔符。
    """
    text = text.strip()

    # 移除「アンコール:」等前綴
    text = _PREFIX_RE.sub("", text).strip()

    # 「曲名」歌手 或 「曲名」/ 歌手
    bracket_match = re.match(r"[「『](.+?)[」』]\s*[/／\-]?\s*(.+)?", text)
    if bracket_match:
        title = bracket_match.group(1).strip()
        artist = (bracket_match.group(2) or "").strip()
        return title, artist

    # 嘗試各種分隔符 (精確匹配, 空白包圍)
    for sep in _SEPARATORS:
        if sep in text:
            parts = text.split(sep, 1)
            return parts[0].strip(), parts[1].strip()

    # 寬鬆 "/" 匹配: 處理 "曲名。/ 歌手" "曲名]/ 歌手" 等變體
    # 允許 "/" 前面緊接標點或括號（無空白）
    loose_match = re.search(r"(.+?)\s*[/／]\s+(.+)", text)
    if loose_match:
        return loose_match.group(1).strip(), loose_match.group(2).strip()

    return text, ""


def parse_comment(text: str) -> list[SongEntry] | None:
    """解析留言文字，擷取歌曲列表。

    Args:
        text: 留言原始文字。

    Returns:
        解析出的歌曲列表，若非セトリ留言則返回 None。
    """
    if not text:
        return None

    # 移除 hashtag 行
    cleaned = _HASHTAG_LINE_RE.sub("", text)

    # 移除裝飾 emoji (但保留文字)
    cleaned = _DECORATION_RE.sub("", cleaned)

    # 先嘗試帶結束時間的格式 (00:02:30 - 00:06:47 01. title - artist)
    range_matches = _RANGE_TIMESTAMP_RE.findall(cleaned)
    # 若帶結束時間的比較多，優先使用
    plain_matches = _TIMESTAMP_LINE_RE.findall(cleaned)
    matches = range_matches if len(range_matches) >= len(plain_matches) * 0.5 and len(range_matches) >= 3 else plain_matches

    if not matches:
        return None

    songs: list[SongEntry] = []
    for ts_str, rest in matches:
        seconds = timestamp_to_seconds(ts_str)

        # 跳過 0:00 (通常是配信開始標記)
        if seconds == 0:
            continue

        # 清理 rest
        rest = rest.strip()

        # 移除編號前綴 (01. 02. 等)
        rest = _NUMBERING_RE.sub("", rest).strip()

        # 分離曲名與歌手
        title, artist = _split_title_artist(rest)

        if not title:
            continue

        # 過濾非歌曲項目 (配信標記、雜談)
        # 無歌手時判定更嚴格，但不完全排除 (保留可能的原創曲)
        if not _is_likely_song(title, has_artist=bool(artist)):
            continue

        songs.append(SongEntry(
            timestamp=ts_str,
            seconds=seconds,
            title_raw=title,
            artist_raw=artist,
        ))

    # 至少 3 曲才視為セトリ
    if len(songs) < 3:
        return None

    if len(songs) < 3:
        return None

    return songs


def pick_best_comment(comments: list[dict]) -> list[SongEntry] | None:
    """從多則留言中選出最佳セトリ。

    Args:
        comments: YouTube commentThreads API 回傳的留言清單。
            每則需含 snippet.topLevelComment.snippet:
                - textOriginal: str
                - likeCount: int
                - authorChannelId.value: str

    Returns:
        最佳留言解析出的歌曲列表，若無有效留言則返回 None。
    """
    best_songs: list[SongEntry] | None = None
    best_score = -1

    for comment in comments:
        snippet = comment.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        text = snippet.get("textOriginal", "")
        like_count = snippet.get("likeCount", 0)
        author_channel = snippet.get("authorChannelId", {}).get("value", "")

        songs = parse_comment(text)
        if songs is None:
            continue

        # 評分
        score = len(songs) * 2 + like_count
        # 頻道擁有者留言加分 (需外部傳入 channel_id 比對，此處預留)
        # if author_channel == channel_owner_id:
        #     score += 10

        if score > best_score:
            best_score = score
            best_songs = songs

    return best_songs


def pick_best_comment_with_owner(
    comments: list[dict], channel_owner_id: str = ""
) -> list[SongEntry] | None:
    """從多則留言中選出最佳セトリ (含頻道擁有者加分)。"""
    best_songs: list[SongEntry] | None = None
    best_score = -1

    for comment in comments:
        snippet = comment.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
        text = snippet.get("textOriginal", "")
        like_count = snippet.get("likeCount", 0)
        author_channel = snippet.get("authorChannelId", {}).get("value", "")

        songs = parse_comment(text)
        if songs is None:
            continue

        score = len(songs) * 2 + like_count
        if channel_owner_id and author_channel == channel_owner_id:
            score += 10

        if score > best_score:
            best_score = score
            best_songs = songs

    return best_songs
