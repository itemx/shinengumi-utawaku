#!/usr/bin/env python3
"""維護 data/song_meta.json — 每首歌 (title, artist) 的 tags 與 duration。

- 掃描所有演唱紀錄，收集不重複 (title, artist)。
- 對 song_meta.json 缺少的項目補上空白骨架 (tags:[], durationSec:null)。
- 保留已填的 tags/durationSec，不覆蓋。
- 冪等，可隨資料庫成長重跑。

用法:
    python scripts/build_song_meta.py            # 補新歌骨架
    python scripts/build_song_meta.py --validate # 只檢查，不寫入
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
SONGS_DIR = DATA_DIR / "songs"
META_PATH = DATA_DIR / "song_meta.json"

# 受控 tag 字彙 (英文，見 COORDINATION.md / SONG_META_GUIDE.md)
ALLOWED_TAGS = [
    "anime", "vocaloid", "game", "tokusatsu", "idol",
    "j-pop", "k-pop", "western", "touhou", "doujin", "original", "ballad",
]


def _key(title: str, artist: str) -> str:
    return title + "\t" + artist


def collect_songs() -> list[tuple[str, str]]:
    seen: dict[str, tuple[str, str]] = {}
    for p in sorted(SONGS_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for v in data.get("videos", []):
            for s in v.get("songs", []):
                t = (s.get("title") or "").strip()
                a = (s.get("artist") or "").strip()
                if t:
                    seen.setdefault(_key(t, a), (t, a))
    return sorted(seen.values())


def load_meta() -> dict[str, dict]:
    if META_PATH.exists():
        arr = json.loads(META_PATH.read_text(encoding="utf-8"))
        return {_key(m["title"], m.get("artist", "")): m for m in arr}
    return {}


def validate(meta: dict[str, dict]) -> list[str]:
    errors: list[str] = []
    for m in meta.values():
        for tag in m.get("tags", []):
            if tag not in ALLOWED_TAGS:
                errors.append(f"未知 tag {tag!r} @ {m['title']} / {m.get('artist','')}")
        d = m.get("durationSec")
        if d is not None and (not isinstance(d, int) or d <= 0 or d > 3600):
            errors.append(f"durationSec 異常 {d!r} @ {m['title']}")
    return errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true", help="只檢查不寫入")
    args = ap.parse_args()

    meta = load_meta()
    songs = collect_songs()

    added = 0
    for title, artist in songs:
        k = _key(title, artist)
        if k not in meta:
            meta[k] = {"title": title, "artist": artist, "tags": [], "durationSec": None}
            added += 1

    errors = validate(meta)
    filled = sum(1 for m in meta.values() if m.get("tags") or m.get("durationSec"))

    print(f"不重複曲目: {len(songs)}")
    print(f"song_meta 項目: {len(meta)} (新增 {added})")
    print(f"已補 (有 tag 或 duration): {filled}")
    if errors:
        print(f"⚠ {len(errors)} 個問題:")
        for e in errors[:20]:
            print("  ", e)

    if args.validate:
        return

    out = sorted(meta.values(), key=lambda m: (m["title"], m.get("artist", "")))
    META_PATH.write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✓ 寫入 {META_PATH}")


if __name__ == "__main__":
    main()
