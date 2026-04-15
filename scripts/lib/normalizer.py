"""曲名正規化模組。

NFKC 正規化、裝飾清理、aliases.json 查表。
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


@dataclass
class NormalizeResult:
    title: str
    artist: str
    matched: bool  # 至少 title 或 artist 在 alias 中命中


# 尾部標註正則: 括號形式 (cover), (short ver.), (THE FIRST TAKE), (JPN Ver.) 等
_TAIL_ANNOTATION_RE = re.compile(
    r"\s*[\(（]"
    r"(?:cover|カバー|short\s*ver\.?|short|acoustic|弾き語り\s*ver\.?|piano\s*ver\.?|ピアノ|"
    r"full|フル|original\s*ver\.?|THE FIRST TAKE|[A-Z]+ [Vv]er\.?|"
    r"M@STER\s*VERSION|long\s*ver[:\.]?|[A-Z]{2,}\s+ver\.?|"
    r"アカペラ\??|a\s*cappella\??|"
    r".+\s+[Cc]over)"
    r"[\)）]\s*$",
    re.IGNORECASE,
)

# Dash 形式的 ver 標記: " - Piano Ver. -", " –Piano ver.–", " ~Yui final ver.~"
# 支援 hyphen(-), en-dash(–), em-dash(—), tilde(~,〜)
_DASH_VER_RE = re.compile(
    r"\s*[-–—~〜]\s*(?:[\w\s]*?\s+)?(?:Piano|Acoustic|弾き語り|ピアノ|original|final)\s*Ver\.?\s*[-–—~〜]?\s*$",
    re.IGNORECASE,
)

# 方括號形式: "[original ver.]", "[Piano Ver.]"
_BRACKET_VER_RE = re.compile(
    r"\s*\[(?:[\w\s]*?\s+)?(?:Piano|Acoustic|弾き語り|ピアノ|original)\s*Ver\.?\]\s*$",
    re.IGNORECASE,
)

# 空白形式: "曲名 Piano Ver."
_SPACE_VER_RE = re.compile(
    r"\s+(?:Piano|Acoustic|弾き語り|ピアノ)\s+Ver\.?\s*$",
    re.IGNORECASE,
)

# TVアニメ / 映画 等出處標註: (TVアニメ「xxx」OP), (ギルティクラウン OP), (ウタ from ONE PIECE...) 等
_MEDIA_SOURCE_RE = re.compile(
    r"\s*[\(（](?:"
    r"(?:TVアニメ|TV|アニメ|映画|劇場版|ゲーム).+?"  # TVアニメ「xxx」OP
    r"|.+?\s+(?:OP|ED|挿入歌|主題歌)"               # xxx OP/ED
    r"|ウタ\s+from\s+.+?"                            # ウタ from ONE PIECE
    r")[\)）]\s*$",
)

# 羅馬拼音/英文翻譯括號: 尾部 (Latin text)
# 括號內容為純 Latin (含帶變音符的拉丁字母如 ā ō ū)，且標題中含有日文字時才移除
_ROMANIZATION_PAREN_RE = re.compile(
    r"\s*[\(（]([A-Za-z\u00C0-\u024F][A-Za-z\u00C0-\u024F\s,.\-'!?&]+)[\)）]\s*$",
)
_HAS_JAPANESE_RE = re.compile(r"[\u3000-\u9FFF\u30A0-\u30FF\u3040-\u309F]")

# 曲名前綴: アニメ『xxx』OP/ED/挿入歌 + 曲名
_MEDIA_PREFIX_RE = re.compile(
    r"^(?:アニメ|TVアニメ|映画|劇場版|ゲーム)[『「].+?[』」].*?(?:OP|ED|挿入歌|主題歌)[　\s]+",
)

# feat. 在曲名中的標記 (移到歌手欄或直接移除)
_FEAT_IN_TITLE_RE = re.compile(
    r"\s+feat\.?\s+.+$", re.IGNORECASE,
)

# feat. 括號形式: (feat. かぴ), (feat. xxx)
_FEAT_PAREN_RE = re.compile(
    r"\s*[\(（]feat\.?\s+.+?[\)）]\s*$", re.IGNORECASE,
)

# 前後引號/裝飾括號
_QUOTE_CHARS = "「」『』""''\u300c\u300d\u300e\u300f"


def load_aliases(path: Path | str) -> dict[str, dict[str, str]]:
    """從 aliases.json 載入並建立反向查找字典。

    Returns:
        {"songs": {alias_lower: canonical, ...}, "artists": {alias_lower: canonical, ...}}
    """
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)

    result: dict[str, dict[str, str]] = {"songs": {}, "artists": {}}
    for category in ("songs", "artists"):
        for canonical, aliases in raw.get(category, {}).items():
            for alias in aliases:
                result[category][alias.lower()] = canonical
    return result


def _clean_text(text: str, is_title: bool = False) -> str:
    """基礎清理。

    Args:
        text: 原始文字。
        is_title: 若為 True，額外清理曲名特有的標註 (出處、拼音等)。
    """
    # NFKC 正規化 (全形英數自動轉半形)
    text = unicodedata.normalize("NFKC", text)
    # 移除 zero-width 字元 (U+200B~U+200D, U+FEFF, U+00AD, U+2060, U+180E)
    text = re.sub(r"[\u200B-\u200D\uFEFF\u00AD\u2060\u180E]", "", text)
    # Wave dash (U+301C) / fullwidth tilde (U+FF5E) → ASCII tilde
    text = text.replace("\u301C", "~").replace("\uFF5E", "~")
    # strip
    text = text.strip()
    # 連續空白合一
    text = re.sub(r"\s+", " ", text)
    # 移除前後引號裝飾
    text = text.strip(_QUOTE_CHARS)
    # 移除尾部標註 (各種 ver 格式)
    text = _TAIL_ANNOTATION_RE.sub("", text)
    text = _DASH_VER_RE.sub("", text)
    text = _BRACKET_VER_RE.sub("", text)
    text = _SPACE_VER_RE.sub("", text)
    if is_title:
        # 移除 TVアニメ 等出處標註 (尾部)
        text = _MEDIA_SOURCE_RE.sub("", text)
        # 移除 アニメ『xxx』挿入歌 等前綴
        text = _MEDIA_PREFIX_RE.sub("", text)
        # 移除羅馬拼音/英文翻譯括號 (標題含日文字 + 尾部純 Latin 括號)
        if _HAS_JAPANESE_RE.search(text):
            text = _ROMANIZATION_PAREN_RE.sub("", text)
        # 移除 feat. (保留原始歌手欄的 feat.)
        text = _FEAT_PAREN_RE.sub("", text)
        text = _FEAT_IN_TITLE_RE.sub("", text)
    # 歌手欄清理
    if not is_title:
        # 先移除 feat. 及之後的內容 (Vocaloid 名等)
        text = re.sub(r"\s+feat\.?\s+.+$", "", text, flags=re.IGNORECASE)
        # 再移除羅馬拼音括號 (feat. 移除後，尾部可能才暴露出拼音括號)
        if _HAS_JAPANESE_RE.search(text):
            text = _ROMANIZATION_PAREN_RE.sub("", text)
    return text.strip()


def normalize(
    title_raw: str, artist_raw: str, aliases: dict[str, dict[str, str]]
) -> NormalizeResult:
    """正規化曲名與歌手名。

    Args:
        title_raw: 原始曲名。
        artist_raw: 原始歌手名。
        aliases: load_aliases() 回傳的反向查找字典。

    Returns:
        NormalizeResult
    """
    title = _clean_text(title_raw, is_title=True)
    artist = _clean_text(artist_raw, is_title=False)

    title_matched = False
    artist_matched = False

    # 查表: title
    songs_lookup = aliases.get("songs", {})
    canonical_title = songs_lookup.get(title.lower())
    if canonical_title:
        title = canonical_title
        title_matched = True

    # 查表: artist
    artists_lookup = aliases.get("artists", {})
    canonical_artist = artists_lookup.get(artist.lower())
    if canonical_artist:
        artist = canonical_artist
        artist_matched = True

    return NormalizeResult(
        title=title,
        artist=artist,
        matched=title_matched or artist_matched,
    )


def load_known_songs(path: Path | str) -> dict[str, str]:
    """從 known_songs.json 建立曲名→歌手的查找表。

    只收錄「該曲名只對應一位歌手」的項目，避免歧義。

    Returns:
        {title_lower: artist}
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    # 同一曲名對應幾位不同歌手？
    title_artists: dict[str, set[str]] = {}
    for entry in data.get("songs", []):
        title = entry.get("title", "").strip()
        artist = entry.get("artist", "").strip()
        if title and artist:
            key = title.lower()
            if key not in title_artists:
                title_artists[key] = set()
            title_artists[key].add(artist)

    # 只保留唯一歌手的
    return {
        k: next(iter(v))
        for k, v in title_artists.items()
        if len(v) == 1
    }


def fill_missing_artist(
    title: str, artist: str, known: dict[str, str]
) -> str:
    """若歌手為空，嘗試從 known_songs 補全。"""
    if artist:
        return artist
    return known.get(title.lower(), "")
