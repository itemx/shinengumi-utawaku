"""歌ってみた（cover）影片標題解析器。

從影片標題中提取曲名和歌手（原唱）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class CoverInfo:
    title: str       # 曲名
    artist: str      # 原唱歌手 (若能從 hashtag 或標題提取)
    is_short: bool   # 是否為 Shorts


def parse_cover_title(video_title: str) -> CoverInfo | None:
    """解析歌ってみた影片標題，提取曲名和歌手。

    支援模式:
        1. 神の眷属が {曲名} [を] 歌ってみた ...
        2. 【 #歌ってみた 】{曲名}【 VTuber名 】
        3. 【 #新人vtuber 】{曲名}【 VTuber名 】 歌ってみた
        4. {曲名} cover #shorts #歌ってみた ...
        5. 【 #歌ってみた 】{曲名} / covered by VTuber名【...】

    Returns:
        CoverInfo 或 None（若不是歌ってみた影片）。
    """
    title = video_title.strip()

    # 判斷是否為 cover 影片
    if not re.search(r"歌ってみた|[Cc]over", title):
        return None

    is_short = bool(re.search(r"#shorts|#Shorts", title))

    song = ""
    artist = ""

    # 模式 1: 「神の眷属が {曲名} [を] [#]歌ってみた」— 全是 Short 風格
    m = re.match(r"^神の眷属が\s*(.+?)\s*(?:を\s*)?(?:#?歌ってみた|歌ってみた)", title)
    if m:
        song = _clean_song_name(m.group(1))
        is_short = True  # 此模式一律視為 Short

    # 模式 2: 「【 #歌ってみた 】{曲名}【」
    if not song:
        m = re.search(r"【\s*#?歌ってみた\s*】\s*(.+?)\s*【", title)
        if m:
            song = _clean_song_name(m.group(1))
            if " / covered by" in song.lower() or " / cover" in song.lower():
                song = song.split("/")[0].strip()

    # 模式 3: 「【 #新人vtuber 】{曲名}【 VTuber名 】 歌ってみた」
    if not song:
        m = re.search(r"【\s*#?\w+\s*】\s+(.+?)\s+【", title)
        if m and "歌ってみた" in title:
            song = _clean_song_name(m.group(1))
            if "-" in song and not song.startswith("-"):
                parts = song.split("-", 1)
                artist = parts[1].strip()
                song = parts[0].strip()

    # 模式 4: 「{曲名} / {歌手} Covered by VTuber【歌ってみた】」
    # 或 「{曲名} / {歌手} Covered」(不帶歌ってみた)
    if not song:
        m = re.match(r"^(?:【[^】]*】\s*)?(.+?)\s*/\s*(.+?)\s+[Cc]overed", title)
        if m:
            song = _clean_song_name(m.group(1))
            artist = m.group(2).strip()
            # 清理歌手名裡的多餘資訊 (如 "鈴木このみ Covered" → "鈴木このみ")
            artist = re.sub(r"\s*[Cc]overed.*$", "", artist).strip()

    # 模式 5: 「【LIVE】{曲名} - VTuber cover【深淵組】」
    if not song:
        m = re.match(r"^【[^】]*】\s*(.+?)\s*[-/]\s*.+?cover", title, re.IGNORECASE)
        if m:
            song = _clean_song_name(m.group(1))

    # 模式 6: 「{曲名} cover #shorts #歌ってみた」— 通常是 Short
    if not song:
        m = re.match(r"^(.+?)\s+cover\s+#", title, re.IGNORECASE)
        if m:
            song = _clean_song_name(m.group(1))
            is_short = True

    # 模式 5: 「{曲名}/cover #歌ってみた」(無空白) — 通常是 Short
    if not song:
        m = re.match(r"^(.+?)/cover\s+#", title, re.IGNORECASE)
        if m:
            song = _clean_song_name(m.group(1))
            is_short = True

    if not song:
        return None

    # 用曲名過濾 hashtag 中的歌手候選
    if not artist:
        artist = _extract_artist_from_hashtags(title, song_title=song)

    return CoverInfo(title=song, artist=artist, is_short=is_short)


def parse_original_song(
    video_title: str, description: str = "", duration_iso: str = ""
) -> CoverInfo | None:
    """解析原創曲影片，從標題和描述中判斷。

    原創曲特徵:
        - 描述含「オリジナル」「original」
        - 不含「歌ってみた」「cover」(已由 parse_cover_title 處理)
        - 影片長度 < 10 分鐘 (長影片通常是直播/活動，不是單曲 MV)
        - 標題通常是「{曲名} {修飾語}」

    Returns:
        CoverInfo 或 None。
    """
    title = video_title.strip()

    # 排除已經是 cover/歌ってみた 的影片
    if re.search(r"歌ってみた|cover\b", title, re.IGNORECASE):
        return None

    # 標題直接含 Original Song
    m = re.match(r"^【[^】]*[Oo]riginal\s*[Ss]ong[^】]*】\s*(.+?)(?:\s*/\s*.+)?$", title)
    if m:
        song = m.group(1).strip()
        # 移除 "Official MV" 等後綴
        song = re.sub(r"\s*(?:Official\s*MV|MV|Music\s*Video).*$", "", song, flags=re.IGNORECASE).strip()
        if song:
            return CoverInfo(title=song, artist="", is_short=False)

    # 長影片 (>10 分鐘) 排除 — 可能是直播/活動而非單曲 MV
    if duration_iso:
        import re as _re
        m = _re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_iso)
        if m:
            hours = int(m.group(1) or 0)
            minutes = int(m.group(2) or 0)
            total_min = hours * 60 + minutes
            if total_min >= 10:
                return None

    # 描述裡含 オリジナル/original 才算原創曲
    desc_lower = description.lower()
    if not re.search(r"オリジナル|original", desc_lower):
        return None

    # 標題解析: 嘗試提取曲名
    song = title

    # 移除常見後綴: 「VTuber名 + Ver.」「MV」「Music Video」
    song = re.sub(r"\s*[\(（【\[]?(?:MV|Music\s*Video|Lyric\s*Video|Full\s*ver\.?)[\)）】\]]?\s*$", "", song, flags=re.IGNORECASE)
    # 移除「!! VTuber名ソロVer.」等
    song = re.sub(r"\s*!+\s*.+(?:Ver\.|ver\.|版)$", "", song)
    # 移除「/ VTuber名」
    song = re.sub(r"\s*/\s*[^/]+$", "", song)
    # 移除「【VTuber名】」
    song = re.sub(r"\s*【[^】]+】\s*$", "", song)

    song = song.strip()
    if not song:
        return None

    is_short = bool(re.search(r"#shorts|#Shorts", title))

    return CoverInfo(title=song, artist="", is_short=is_short)


def _clean_song_name(name: str) -> str:
    """清理曲名。"""
    # 移除 hashtag
    name = re.sub(r"\s*#\S+", "", name)
    # 移除多餘空白
    name = re.sub(r"\s+", " ", name).strip()
    # 移除 remix/ver 等標註 (保留原名)
    # 不移除，因為有些是有意義的 (如 "CPK ! Remix")
    return name


def _extract_artist_from_hashtags(title: str, song_title: str = "") -> str:
    """從 hashtag 中嘗試提取原唱歌手名。

    常見模式: #星街すいせい #deco27 #ado 等出現在曲名 hashtag 附近。
    排除明顯不是歌手的 tag。
    """
    # 排除的 hashtag (非歌手)
    exclude = {
        "歌ってみた", "shorts", "cover", "新人vtuber", "vtuber", "vsinger",
        "ボカロ", "karaoke", "歌枠", "渉海よひら", "深淵組", "超かぐや姫",
        "プロセカ", "シャニマス", "学マス", "初見歓迎",
    }

    # 提取所有 hashtag
    tags = re.findall(r"#(\S+)", title)

    candidates = []
    exclude_lower = {e.lower() for e in exclude}
    for tag in tags:
        tag_clean = tag.rstrip("】）)")  # 清理殘留括號
        # 處理 "#渉海よひら/深淵組" 這類複合 tag
        sub_tags = re.split(r"[/／]", tag_clean)
        for st in sub_tags:
            st = st.strip().rstrip("】）)")
            if not st:
                continue
            if st.lower() in exclude_lower:
                continue
            candidates.append(st)

    if not candidates:
        return ""

    # 過濾掉跟曲名重複的 (避免 歌手=曲名)
    if song_title:
        song_lower = song_title.lower()
        candidates = [c for c in candidates if c.lower() != song_lower]

    if not candidates:
        return ""

    # 歌手 tag 通常在曲名 tag 之後，取最後一個
    return candidates[-1]
