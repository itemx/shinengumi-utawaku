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
  `anime vocaloid game tokusatsu idol j-pop western touhou doujin original ballad`
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
| `western` | `洋楽` |
| `touhou` | `東方` |
| `doujin` | `同人` |
| `original` | `オリジナル` |
| `ballad` | `バラード` |

### 分類與查證原則

- 一首歌可以有多個 tag，但只能從上述 11 個選取。
- 有明確作品來源時，加上對應來源 tag；一般日文流行曲加 `j-pop`，西洋歌曲加 `western`。
- 資訊不明時寧可少加，不以推測補類別。
- `durationSec` 查證優先順序：官方 YouTube Audio／官方藝人或唱片公司頁／正式串流平台頁。
- 有多個正式版本時，採最初正式發行的標準版。
- Codex 依 `song_meta.json` 既有順序分批查證，保留每首歌的來源紀錄供複核。

### 交接要求

- **Claude** 必須將 `scripts/build_song_meta.py` 的 `ALLOWED_TAGS` 與 `data/SONG_META_GUIDE.md` 同步改為上述英文詞彙，之後再以 `python scripts/build_song_meta.py --validate` 驗證。
- **Codex** 在驗證器同步前，不得將英文 tag 寫入 `data/song_meta.json`。

## 推送紀律（兩邊都遵守）

- 每次 push 前 `git pull --rebase`。
- 小步 commit。
- 碰 `data/songs/*` 就順手重生衍生檔再一起提交。
- 要動對方負責的檔案，先在對話裡講一聲換手。
