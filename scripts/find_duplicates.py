#!/usr/bin/env python3
"""重複曲目の疑いを洗い出す。

同じ曲が別表記で 2 曲に割れているものを探す。次の 2 種類を拾う:

1. 正規化し直すと既存の別の曲になる行
   （正規化ルールが後から増えたのに、古い行が昔の表記のまま残っている。例: 千本桜 feat.初音ミク）
2. 表記ゆれ
   曲名を「大文字小文字・全角半角・カタカナ/ひらがな・発音記号・空白と記号」を無視して比べて同じで、
   歌手が同じ／片方が空／片方がもう片方を含む（例: じん と じん feat.Lia）

同名でも歌手がまったく違う曲（別の曲）は拾わない。
確認済みで「別の曲」と判断したものは data/not_duplicates.json に入れておくと以後は出ない。

用法:
    python scripts/find_duplicates.py              # 標準出力に一覧
    python scripts/find_duplicates.py --report x.md  # CI 用 Markdown（候補なしなら空ファイル）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.lib.normalizer import load_aliases, normalize

DATA_DIR = Path(__file__).parent.parent / "data"
SONGS_DIR = DATA_DIR / "songs"
IGNORE_PATH = DATA_DIR / "not_duplicates.json"


def fold(s: str) -> str:
    """比較用のキー。表記ゆれになりやすい差を全部落とす"""
    s = unicodedata.normalize("NFKC", s).lower()
    s = re.sub(r"[ァ-ヶ]", lambda m: chr(ord(m.group()) - 0x60), s)       # カタカナ → ひらがな
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not 0x300 <= ord(c) <= 0x36F)
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"[\W_]+", "", s)                                          # 空白・記号


def load_rows() -> list[dict]:
    rows = []
    for p in sorted(SONGS_DIR.glob("*.json")):
        data = json.loads(p.read_text(encoding="utf-8"))
        for v in data.get("videos", []):
            for s in v.get("songs", []):
                rows.append({
                    "title": s.get("title", ""), "artist": s.get("artist", ""),
                    "titleRaw": s.get("titleRaw", ""), "artistRaw": s.get("artistRaw", ""),
                    "videoId": v["videoId"], "date": v.get("publishedAt", "")[:10],
                })
    return rows


def load_ignored() -> set[frozenset]:
    if not IGNORE_PATH.exists():
        return set()
    pairs = json.loads(IGNORE_PATH.read_text(encoding="utf-8"))
    return {frozenset((tuple(a), tuple(b))) for a, b in pairs}


def find(rows: list[dict]) -> list[dict]:
    """候補を返す。各候補は {kind, a: (title, artist), b: (title, artist), note}"""
    aliases = load_aliases(DATA_DIR / "aliases.json")
    count: dict[tuple, int] = defaultdict(int)
    for r in rows:
        count[(r["title"], r["artist"])] += 1
    songs = set(count)
    ignored = load_ignored()
    out: dict[frozenset, dict] = {}

    def add(kind, a, b, note):
        key = frozenset((a, b))
        if a != b and key not in ignored and key not in out:
            out[key] = {"kind": kind, "a": a, "b": b, "note": note}

    # 1. 正規化し直すと既存の別の曲になる。
    #    ただし「削られただけ」（feat. 等が落ちた）に限る。歌手がまるごと違うものは、
    #    元の入力が間違っていて人の手で直した行（Pray / 水樹奈々 等）なので拾わない
    for r in rows:
        if not r["titleRaw"]:
            continue
        n = normalize(r["titleRaw"], r["artistRaw"], aliases)
        cur, new = (r["title"], r["artist"]), (n.title, n.artist)
        if new != cur and new in songs and all(fold(x) in fold(y) for x, y in zip(new, cur)):
            add("stale", cur, new, f"{r['videoId']} {r['date']}")

    # 2. 表記ゆれ（曲名の fold が同じで、歌手が同じ／空／包含）
    by_title: dict[str, list[tuple]] = defaultdict(list)
    for k in songs:
        by_title[fold(k[0])].append(k)
    for group in by_title.values():
        group.sort()
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                fa, fb = fold(a[1]), fold(b[1])
                if fa == fb or not fa or not fb or (min(len(fa), len(fb)) >= 2 and (fa in fb or fb in fa)):
                    add("variant", a, b, f"{count[a]} 回 / {count[b]} 回")
    return sorted(out.values(), key=lambda c: (c["kind"], c["a"]))


def fmt(k: tuple) -> str:
    return f"{k[0]} / {k[1]}" if k[1] else k[0]


def report(cands: list[dict]) -> str:
    if not cands:
        return ""
    label = {"stale": "正規化し直すと既存曲になる", "variant": "表記ゆれ"}
    lines = [
        f"重複曲目の疑いが **{len(cands)} 件** あります。",
        "",
        "| 種類 | 曲 A | 曲 B | 備考 |",
        "| --- | --- | --- | --- |",
    ]
    for c in cands:
        lines.append(f"| {label[c['kind']]} | {fmt(c['a'])} | {fmt(c['b'])} | {c['note']} |")
    lines += [
        "",
        "---",
        "同じ曲なら `data/songs/*.json` を直して（必要なら `data/aliases.json` にも追加）、",
        "`song_meta.json` の重複項目をまとめてください。",
        "別の曲なら `data/not_duplicates.json` に `[[曲名, 歌手], [曲名, 歌手]]` を追加すると以後は出ません。",
        "この issue は次回スキャン時に自動更新／自動クローズされます。",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", metavar="PATH", help="Markdown を書き出す（候補なしなら空ファイル）")
    args = ap.parse_args()
    cands = find(load_rows())
    if args.report:
        Path(args.report).write_text(report(cands), encoding="utf-8")
    for c in cands:
        print(f"[{c['kind']}] {fmt(c['a'])}  <->  {fmt(c['b'])}   ({c['note']})")
    print(f"候補 {len(cands)} 件")


if __name__ == "__main__":
    main()
