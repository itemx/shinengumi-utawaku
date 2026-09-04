#!/usr/bin/env bash
# 未補完の song_meta を GitHub issue で追跡する。
#
# すでに open な追跡 issue に載っている曲は再掲せず、残りがあるときだけ
# 新しい issue を立てる（Codex に同じ曲を二度調べさせないため）。
# 全曲補完されたら、開いている追跡 issue をまとめてクローズする。
#
# scan.yml（3 日ごと）と ingest-submission.yml（投稿入庫後）の両方から呼ぶ。
# ローカルからも実行可: gh の認証さえ通っていればよい。
set -euo pipefail

cd "$(dirname "$0")/../.."

PREFIX='song_meta 未補完'
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# 現在 open な追跡 issue の本文を集める（この表から掲載済みの曲を割り出す）
gh issue list --state open --limit 100 --json number,title,body \
  -q ".[] | select(.title | startswith(\"$PREFIX\")) | .body" > "$TMP/open.md"

open_numbers=$(gh issue list --state open --limit 100 --json number,title \
  -q ".[] | select(.title | startswith(\"$PREFIX\")) | .number")

# 全体の未補完（除外なし）— これが空なら追跡 issue は用済み
python scripts/build_song_meta.py --report "$TMP/all.md" > /dev/null
if [ ! -s "$TMP/all.md" ]; then
  for n in $open_numbers; do
    gh issue close "$n" --comment '全曲補完済み 🎉'
  done
  echo "未補完なし"
  exit 0
fi

# 掲載済みを除いた差分だけを新しい issue にする
python scripts/build_song_meta.py --report "$TMP/new.md" --exclude "$TMP/open.md"
if [ ! -s "$TMP/new.md" ]; then
  echo "未補完はあるが、すべて既存 issue に掲載済み"
  exit 0
fi

gh issue create --title "$PREFIX ($(date -u +%Y-%m-%d))" --body-file "$TMP/new.md"
