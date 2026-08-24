# 協作分工 (Claude ↔ Codex)

兩個 AI agent 共用同一個 repo / 本機路徑 / main 分支。為避免撞檔，遵守以下分工。

## 檔案負責歸屬

| 區域 | 負責 | 備註 |
|---|---|---|
| `data/song_meta.json` | **Codex** | 只補 `tags` / `durationSec`，見下方規則 |
| `data/aliases.json` | Claude | 正規化別名，迭代中 |
| `scripts/lib/normalizer.py`, `comment_parser.py`, `title_parser.py` | Claude | 解析/正規化邏輯 |
| `scripts/scan_new.py`, `ingest_issue.py`, `lib/review_issue.py`, `build_*.py` | Claude | 掃描/投稿/審核/建置 |
| `.github/workflows/*.yml` | Claude | CI 流程 |
| `src/pages/plan.astro`, `src/lib/data.ts`, `src/lib/i18n.ts` | Claude | 排歌單功能 (Phase 3 進行中) |
| `data/songs/*.json` | Claude | 內容資料，兩邊同時改必衝突 |
| 其餘 `src/components/*` 視覺、`README.md`、`scripts/tests/*` | 可協商 | 動前先講一聲 |

## 🚫 絕不要手改（自動產生的衍生檔）

- `data/known_songs.json`
- `data/_stats.json`

改了 `data/songs/*` 之後，用指令重生：

```bash
python scripts/build_stats.py && python scripts/build_known_songs.py
```

## Codex 的 song_meta.json 規則

`data/song_meta.json` 是陣列，每首歌一項：

```json
{ "title": "夜に駆ける", "artist": "YOASOBI", "tags": [], "durationSec": null }
```

- **只能填 `tags` 和 `durationSec`。**
- **不可改 `title` / `artist`，不可增刪項目**（項目由 `scripts/build_song_meta.py` 從曲庫產生；改動會跟曲庫對不上、join 漏歌）。
- `tags`：只能用下列英文受控字彙（完全一致的寫法），可複選（OR），不得自行增加類別：
  `anime vocaloid game tokusatsu idol j-pop k-pop western touhou doujin original ballad`
- `durationSec`：原曲正式錄音室標準版的整數秒數（30–3600）；不採現場、翻唱、short 或混音版。查不到或無法可靠確認時填 `null`。
- 詳見 [data/SONG_META_GUIDE.md](data/SONG_META_GUIDE.md)。

補完後 Claude 會跑驗證：

```bash
python scripts/build_song_meta.py --validate
```

## song_meta 查證與分類規格（2026-08-24 起）

### Tag 對照

| English | 舊日文詞彙 |
|---|---|
| `anime` | `アニメ` |
| `vocaloid` | `ボカロ` |
| `game` | `ゲーム` |
| `tokusatsu` | `特撮` |
| `idol` | `アイドル` |
| `j-pop` | `J-POP` |
| `k-pop` | 韓流（2026-08-24 新增） |
| `western` | `洋楽` |
| `touhou` | `東方` |
| `doujin` | `同人` |
| `original` | `オリジナル` |
| `ballad` | `バラード` |

### 分類與查證原則

- 一首歌可以有多個 tag，但只能從上述 12 個選取。
- 有明確作品來源時，加上對應來源 tag；一般日文流行曲加 `j-pop`，西洋歌曲加 `western`。
- 資訊不明時寧可少加，不以推測補類別。
- `durationSec` 查證優先順序：官方 YouTube Audio／官方藝人或唱片公司頁／正式串流平台頁。
- 有多個正式版本時，採最初正式發行的標準版。
- Codex 依 `song_meta.json` 既有順序分批查證，保留每首歌的來源紀錄供複核。

### 交接要求

- **Claude** 必須將 `scripts/build_song_meta.py` 的 `ALLOWED_TAGS` 與 `data/SONG_META_GUIDE.md` 同步改為上述英文詞彙，之後再以 `python scripts/build_song_meta.py --validate` 驗證。（已完成 2026-08-24）
- **Codex** 在驗證器同步前，不得將英文 tag 寫入 `data/song_meta.json`。（驗證器已同步，可寫入）

### 自主連續補完模式（2026-08-24 起，Codex 可一路跑完不用逐批確認）

Codex 可從目前進度（Alchemy 之後那批已完成，下一首 `Booo!` 之後）一路補到最後一首，**不需每批等 Claude 確認**，但須遵守：

1. **每次 push 前自驗**：`python scripts/build_song_meta.py --validate`，通過（0 錯誤）才 commit + push；沒過就修到過。
2. **分段 commit**：建議每 ~100 首一個 commit（不要憋成單一巨大 commit），commit message 標明範圍與是否有 null。
3. **不變量（每次都要成立）**：
   - 只改 `tags` / `durationSec`；**不增刪項目、不改 `title` / `artist`**（項目數固定 1516）。
   - tag 只用英文 12 類；`durationSec` 為 30–3600 整數，或 `null`。
   - push 前 `git pull --rebase`。
4. **時長衝突裁決**：使用者口頭給的粗估與官方查證不一致時，**以官方正式串流／發行標準版為準**（使用者已同意）。查不到官方版才用使用者給的粗估；都沒有就 `null`。
5. **完成後**：用下面的「commit message 信號」通知 Claude（不需要使用者手動轉告）。Claude 會做最終總驗收（tag 合法性＋duration 範圍＋項目數 1516＋title/artist 零變動），通過後接排歌單 Phase 3（tag 篩選＋精準時間估算＋反推模式）。

## Agent 間自動通知（commit message 信號）

用 **commit message 當事件總線**，取代人工轉告。git 是兩邊唯一共用的即時通道。

### 信號格式

在 commit message 中放一行（**必須自己獨立成行，行首開始**）：

| 信號 | 發送方 | 意義 |
|---|---|---|
| `song_meta: COMPLETE` | Codex | song_meta 全部補完，請 Claude 總驗收 |
| `song_meta: NEEDS-CLAUDE <一行說明>` | Codex | 中途卡住／發現規格衝突，需要 Claude 介入 |
| `song_meta: AUDIT-PASS` | Claude | 總驗收通過，Codex 可視為結案 |
| `song_meta: AUDIT-FAIL <一行說明>` | Claude | 驗收未過，Codex 需依說明修正 |

範例：

```
data: finish song_meta enrichment (1516 songs)

song_meta: COMPLETE
```

### 偵測條件（三者皆須成立，否則不會觸發）

1. 標記**自己獨立成一行**（行首開始）。寫在句子中間（例如 `... 標記 "song_meta: COMPLETE" ...`）**不會**被偵測到 —— 這是為了避免文件說明本身誤觸發。
2. 該 commit 必須有變更到 `data/song_meta.json`（純文件 commit 不觸發）。
3. 必須 **push** 到 `origin/main`（只 commit 沒 push 偵測不到）。

### 實作與限制

- **Claude 側**：session 內掛背景輪詢（每 2 分鐘 `git fetch` + 檢查 `origin/main`），命中即自動喚醒，**不需使用者轉告**。限制：只活在該 session；session 結束需重新掛上。
- **Codex 側**：目前**沒有**常駐監看。所以 Claude 發出的 `AUDIT-PASS` / `AUDIT-FAIL`，Codex 請在**每次開工時**主動確認一次：

  ```bash
  git fetch -q origin main && git log origin/main -20 --format='%s%n%b' | grep -E '^song_meta: (AUDIT-PASS|AUDIT-FAIL)'
  ```

- 兩邊都無法保證即時，但信號留在 git 歷史裡不會遺失，開工檢查即可補上。

## 推送紀律（兩邊都遵守）

- 每次 push 前 `git pull --rebase`。
- 小步 commit。
- 碰 `data/songs/*` 就順手重生衍生檔再一起提交。
- 要動對方負責的檔案，先在對話裡講一聲換手。
