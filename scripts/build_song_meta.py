#!/usr/bin/env python3
"""維護 data/song_meta.json — 每首歌 (title, artist) 的 tags 與 duration。

- 掃描所有演唱紀錄，收集不重複 (title, artist)。
- 對 song_meta.json 缺少的項目補上空白骨架 (tags:[], durationSec:null)。
- 保留已填的 tags/durationSec，不覆蓋。
- 冪等，可隨資料庫成長重跑。

用法:
    python scripts/build_song_meta.py            # 補新歌骨架
    python scripts/build_song_meta.py --validate # 只檢查，不寫入
    python scripts/build_song_meta.py --report x.md  # 未補完清單（CI 開 issue 用）
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
    ap.add_argument(
        "--report",
        metavar="PATH",
        help="把未補完清單寫成 Markdown（給 CI 開 issue 用）。隱含 --validate，不寫入 song_meta.json",
    )
    args = ap.parse_args()

    meta = load_meta()
    songs = collect_songs()

    new_keys: set[str] = set()
    for title, artist in songs:
        k = _key(title, artist)
        if k not in meta:
            meta[k] = {"title": title, "artist": artist, "tags": [], "durationSec": None}
            new_keys.add(k)
    added = len(new_keys)

    errors = validate(meta)
    filled = sum(1 for m in meta.values() if m.get("tags") or m.get("durationSec"))

    print(f"不重複曲目: {len(songs)}")
    print(f"song_meta 項目: {len(meta)} (新增 {added})")
    print(f"已補 (有 tag 或 duration): {filled}")

    # 曲庫裡還沒有人唱過的項目。手動先登錄（等這首被唱到就自動接上）也算正常，
    # 所以只列出來供確認，不當成錯誤，也不自動刪除。
    song_keys = {_key(t, a) for t, a in songs}
    orphans = [m for k, m in meta.items() if k not in song_keys]
    if orphans:
        print(f"ℹ 尚無演唱紀錄的項目 {len(orphans)} 筆（預先登錄，不會顯示在網站上）:")
        for m in orphans[:20]:
            print(f"   {m['title']} / {m.get('artist','')}")
    if errors:
        print(f"⚠ {len(errors)} 個問題:")
        for e in errors[:20]:
            print("  ", e)

    if args.report:
        Path(args.report).write_text(_report(meta, new_keys), encoding="utf-8")
        print(f"✓ 報告寫入 {args.report}")
        return

    if args.validate:
        return

    out = sorted(meta.values(), key=lambda m: (m["title"], m.get("artist", "")))
    META_PATH.write_text(_dumps(out), encoding="utf-8")
    print(f"✓ 寫入 {META_PATH}")


MAX_REPORT_ROWS = 100


def _report(meta: dict[str, dict], new_keys: set[str]) -> str:
    """未補完曲目的 Markdown。全部補完時回傳空字串（CI 用 `test -s` 判斷）。

    未補完 = song_meta.json 裡還沒有這筆（新曲）, 或 durationSec 是 null。
    tags 空陣列 **不算未補完** —— 項目已存在代表 Codex 看過了，
    「這首沒有適合的 tag」也是一種結論（例: 一般向 J-POP 以外的雜項）。
    """
    missing = [
        m
        for k, m in meta.items()
        if k in new_keys or m.get("durationSec") is None
    ]
    if not missing:
        return ""

    missing.sort(key=lambda m: (m["title"], m.get("artist", "")))
    rows = [
        "| 曲名 | 歌手 | 新曲 | tags | 長さ |",
        "| --- | --- | --- | --- | --- |",
    ]
    for m in missing[:MAX_REPORT_ROWS]:
        new = "🆕" if _key(m["title"], m.get("artist", "")) in new_keys else ""
        tags = "✅" if m.get("tags") else "❌"
        dur = "✅" if m.get("durationSec") is not None else "❌"
        rows.append(f"| {m['title']} | {m.get('artist','')} | {new} | {tags} | {dur} |")

    extra = len(missing) - MAX_REPORT_ROWS
    tail = f"\n\n…他 {extra} 件（全件は `--report` をローカル実行）" if extra > 0 else ""

    return (
        f"新曲が入ったため **{len(missing)} 件** の song_meta が未補完です。\n\n"
        + "\n".join(rows)
        + tail
        + "\n\n---\n"
        "`data/song_meta.json` を直接編集してください（少量なら Claude、"
        "一括調査が要る規模なら Codex）。Codex が一括で対応した場合は"
        "コミットメッセージに `song_meta: COMPLETE` を入れてください。\n"
        "この issue は次回スキャン時に自動更新／自動クローズされます。\n"
    )


def _dumps(items: list[dict]) -> str:
    """序列化為與 Codex 一致的格式：每筆 4 行，tags 陣列緊湊成一行。

    避免直接用 json.dumps(indent=2) —— 它會把 tags 陣列展開成多行，
    對已有內容造成大量格式雜訊（曾造成 7000+ 行的無意義 diff）。
    """
    lines = ["["]
    for i, m in enumerate(items):
        tags = json.dumps(m.get("tags", []), ensure_ascii=False)
        dur = "null" if m.get("durationSec") is None else str(m["durationSec"])
        title = json.dumps(m["title"], ensure_ascii=False)
        artist = json.dumps(m.get("artist", ""), ensure_ascii=False)
        comma = "," if i < len(items) - 1 else ""
        lines.append(
            "  {\n"
            f"    \"title\": {title},\n"
            f"    \"artist\": {artist},\n"
            f"    \"tags\": {tags},\n"
            f"    \"durationSec\": {dur}\n"
            f"  }}{comma}"
        )
    lines.append("]")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
