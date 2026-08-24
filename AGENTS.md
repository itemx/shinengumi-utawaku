# SEG-V UtaList — Agent 工作守則

VTuber 歌枠曲目資料庫（Astro SSG + Python 資料管線，部署於 GitHub Pages）。

## ⚠️ 開工前必讀

本 repo 由兩個 AI agent（Codex + Claude）共用同一個工作區與 main 分支。

**每次開始工作前，先讀 [COORDINATION.md](COORDINATION.md)** — 裡面定義檔案負責歸屬、
不可手改的衍生檔、song_meta 補完規格與自主連續補完模式、推送紀律。

Codex 重點速記（細節仍以 COORDINATION.md 為準）：

- **你負責 `data/song_meta.json`**：只填 `tags` / `durationSec`，
  **不增刪項目、不改 `title` / `artist`**（項目數固定 1516，由 Claude 的 build 腳本產生）。
- tag 只能用英文 12 類：`anime vocaloid game tokusatsu idol j-pop k-pop western touhou doujin original ballad`
- `durationSec`：官方正式發行標準版整數秒（30–3600），查不到填 `null`。
  與使用者口頭給的粗估衝突時，**以官方正式串流／發行版為準**。
- **自主連續補完模式已授權**：不用每批等確認，但每次 push 前自己跑
  `python scripts/build_song_meta.py --validate`（須 0 錯誤），並每 ~100 首分段 commit。
- **絕不手改**衍生檔 `data/known_songs.json`、`data/_stats.json`。
- 其餘檔案（normalizer / parser、scan 與 ingest 流程、workflows、`src/pages/plan.astro`、
  `src/lib/data.ts`、`src/lib/i18n.ts`、`data/songs/*`、`data/aliases.json`）屬 Claude，
  要動先在對話裡講一聲換手。
- push 前一律 `git pull --rebase`。

## 完成信號（重要：取代人工轉告）

全部補完後，**最後一個 commit 的 message 必須包含這行標記**：

```
song_meta: COMPLETE
```

例如：

```
data: finish song_meta enrichment (1516 songs)

song_meta: COMPLETE
```

Claude 有背景監看在輪詢 `origin/main`，看到這個標記會自動被喚醒並執行最終總驗收，
**不需要使用者手動轉告**。

偵測條件（三者皆須成立，否則不會觸發）：

1. 標記**必須自己獨立成一行**（行首開始）。寫在句子中間（例如 `... 標記 "song_meta: COMPLETE" ...`）**不會**被偵測到。
2. 該 commit 必須有變更到 `data/song_meta.json`（純文件 commit 不觸發）。
3. 必須 **push** 到 `origin/main`（只 commit 沒 push 偵測不到）。

若中途需要 Claude 介入（例如發現規格衝突、驗證一直過不了），同樣可用 commit message 標記：

```
song_meta: NEEDS-CLAUDE <一行說明>
```

### 開工時請先檢查 Claude 的回覆信號

Codex 沒有常駐監看，所以 Claude 的驗收結果要自己來拿。**每次開工先跑這行**：

```bash
git fetch -q origin main && git log origin/main -20 --format='%s%n%b' | grep -E '^song_meta: (AUDIT-PASS|AUDIT-FAIL)'
```

- `song_meta: AUDIT-PASS` → 總驗收通過，可視為結案。
- `song_meta: AUDIT-FAIL <說明>` → 依說明修正後重新 push（並重新附上 `song_meta: COMPLETE`）。

完整信號表與偵測條件見 [COORDINATION.md](COORDINATION.md#agent-間自動通知commit-message-信號)。
