#!/usr/bin/env bash
# 重複曲目の疑いを GitHub issue で追跡する（scripts/find_duplicates.py）。
#
# 疑いがあれば追跡 issue を 1 本だけ持つ: 開いていれば本文を最新に書き換え、無ければ作る。
# 疑いが 0 件になったら開いている追跡 issue を閉じる。
# scan.yml（3 日ごと）から呼ぶ。ローカルからも gh の認証さえあれば実行可。
set -euo pipefail

cd "$(dirname "$0")/../.."

PREFIX='重複曲目の疑い'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

open_number=$(gh issue list --state open --limit 100 --json number,title \
  -q "[.[] | select(.title | startswith(\"$PREFIX\"))][0].number // empty")

python scripts/find_duplicates.py --report "$TMP/dup.md"

if [ ! -s "$TMP/dup.md" ]; then
  if [ -n "$open_number" ]; then
    gh issue close "$open_number" --comment '重複の疑いはなくなりました 🎉'
  fi
  echo "重複の疑いなし"
  exit 0
fi

if [ -n "$open_number" ]; then
  gh issue edit "$open_number" --body-file "$TMP/dup.md"
  echo "issue #$open_number を更新"
else
  gh issue create --title "$PREFIX ($(date -u +%Y-%m-%d))" --body-file "$TMP/dup.md"
fi
