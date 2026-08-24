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
- `tags`：只能用受控字彙（完全一致的寫法），可複選（OR）：
  `アニメ ボカロ ゲーム 特撮 アイドル J-POP 洋楽 東方 同人 オリジナル バラード`
- `durationSec`：原曲錄音室版長度（整數秒，30–3600），查不到填 `null`。
- 詳見 [data/SONG_META_GUIDE.md](data/SONG_META_GUIDE.md)。

補完後 Claude 會跑驗證：

```bash
python scripts/build_song_meta.py --validate
```

## 推送紀律（兩邊都遵守）

- 每次 push 前 `git pull --rebase`。
- 小步 commit。
- 碰 `data/songs/*` 就順手重生衍生檔再一起提交。
- 要動對方負責的檔案，先在對話裡講一聲換手。
