"""aliases.json が既存データを壊さないことを検証する。

alias は曲名だけ／歌手だけを見て一括置換する。そのため「まだ自分の名義で
曲を持っている名前」を別名として登録すると、次の ingest でその曲まで
巻き込まれて別項目に割れる。

実際に起きた例:
    artists: 古川本舗 → ぬー (古川本舗)
    月光食堂 のために入れたが、Alice / あいのけもの / グリグリメガネと月光蟲
    （いずれも 古川本舗 名義）まで ぬー (古川本舗) に書き換えられ、
    7〜18 行あった既存曲から新曲として分離した。
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent.parent / "data"


def _load():
    aliases = json.loads((DATA_DIR / "aliases.json").read_text(encoding="utf-8"))
    titles_by_artist: dict[str, set[str]] = defaultdict(set)
    artists_by_title: dict[str, set[str]] = defaultdict(set)
    for p in sorted((DATA_DIR / "songs").glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for v in data.get("videos", []):
            for s in v.get("songs", []):
                titles_by_artist[s["artist"]].add(s["title"])
                artists_by_title[s["title"]].add(s["artist"])
    return aliases, titles_by_artist, artists_by_title


def test_artist_alias_does_not_hijack_live_artist():
    """別名として登録した歌手名が、まだ自分の曲を持っていてはいけない。"""
    aliases, titles_by_artist, _ = _load()
    offenders = [
        f"{variant!r} → {canonical!r} ({len(titles_by_artist[variant])} 曲がまだ "
        f"{variant!r} 名義: {sorted(titles_by_artist[variant])[:3]})"
        for canonical, variants in aliases.get("artists", {}).items()
        for variant in variants
        if variant != canonical and variant in titles_by_artist
    ]
    assert not offenders, "この alias は既存曲を巻き込む:\n  " + "\n  ".join(offenders)


def test_song_alias_does_not_hijack_live_title():
    """別名として登録した曲名が、まだその曲名で残っていてはいけない。"""
    aliases, _, artists_by_title = _load()
    offenders = [
        f"{variant!r} → {canonical!r} (歌手 {sorted(artists_by_title[variant])} で残存)"
        for canonical, variants in aliases.get("songs", {}).items()
        for variant in variants
        if variant != canonical and variant in artists_by_title
    ]
    assert not offenders, "この alias は既存曲を巻き込む:\n  " + "\n  ".join(offenders)
