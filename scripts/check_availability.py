#!/usr/bin/env python3
"""既存の全動画の公開状態をチェックして data/songs/*.json に記録する。

付与するフィールド (video エントリ直下):
    videoStatus: "unlisted" | "unavailable"

「公開」は正常なので **フィールドを付けない**（既存データを汚さないため）。

YouTube API の制約:
    非公開 (private) と 削除済み (deleted) は API 上で区別できない。
    どちらも結果に含まれないため、まとめて "unavailable" とする。

使い方:
    python scripts/check_availability.py            # 全動画チェック
    python scripts/check_availability.py --dry-run  # 書き込まず結果だけ表示

API 消費: 1 unit / 50 本
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import dotenv_values

from scripts.lib.data_store import DATA_DIR
from scripts.lib.youtube_api import YouTubeClient

SONGS_DIR = DATA_DIR / "songs"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="書き込まずに結果のみ表示")
    args = ap.parse_args()

    os.environ.update({k: v for k, v in dotenv_values(".env").items() if v})
    yt = YouTubeClient()

    # 全 videoId を収集
    files = sorted(SONGS_DIR.glob("*.json"))
    all_ids: list[str] = []
    for p in files:
        data = json.loads(p.read_text(encoding="utf-8"))
        all_ids += [v["videoId"] for v in data.get("videos", [])]

    print(f"対象: {len(all_ids)} 本 (API {(len(all_ids) + 49) // 50} units)")
    status = yt.check_availability(all_ids)

    counts = {"public": 0, "unlisted": 0, "unavailable": 0}
    changes: list[str] = []

    for p in files:
        data = json.loads(p.read_text(encoding="utf-8"))
        dirty = False
        for v in data.get("videos", []):
            st = status.get(v["videoId"], "public")
            counts[st] = counts.get(st, 0) + 1
            prev = v.get("videoStatus")
            new = None if st == "public" else st
            if prev != new:
                changes.append(
                    f"  {v['videoId']}: {prev or 'public'} → {new or 'public'}  {v.get('title','')[:40]}"
                )
                if new is None:
                    v.pop("videoStatus", None)
                else:
                    v["videoStatus"] = new
                dirty = True
        if dirty and not args.dry_run:
            p.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )

    print(f"\n公開: {counts['public']} / 限定公開: {counts['unlisted']} / 視聴不可: {counts['unavailable']}")
    if changes:
        print(f"\n変更 {len(changes)} 件:")
        for c in changes:
            print(c)
    else:
        print("\n変更なし")

    if args.dry_run:
        print("\n(--dry-run のため書き込みなし)")
    print(f"API 消費: {yt.units_consumed} units")


if __name__ == "__main__":
    main()
