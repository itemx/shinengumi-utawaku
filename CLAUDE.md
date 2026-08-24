# SEG-V UtaList

VTuber 歌枠曲目資料庫（Astro SSG + Python 資料管線，部署於 GitHub Pages）。

## ⚠️ 開工前必讀

本 repo 由兩個 AI agent（Claude + Codex）共用同一個工作區與 main 分支。

**每次開始工作前，先讀 [COORDINATION.md](COORDINATION.md)** — 裡面定義檔案負責歸屬、
不可手改的衍生檔、song_meta 補完規格、推送紀律。違反會造成撞檔或資料不一致。

重點速記（細節仍以 COORDINATION.md 為準）：

- `data/song_meta.json` 是 **Codex** 的；Claude 只跑 `python scripts/build_song_meta.py --validate` 驗證與提交，**不編輯內容**。
- **絕不手改**衍生檔 `data/known_songs.json`、`data/_stats.json`；改完 `data/songs/*` 後用
  `python scripts/build_stats.py && python scripts/build_known_songs.py` 重生。
- Claude 負責：normalizer / parser、scan 與 ingest 流程、workflows、`src/pages/plan.astro`、
  `src/lib/data.ts`、`src/lib/i18n.ts`、`data/songs/*`、`data/aliases.json`。
- push 前一律 `git pull --rebase`。

## 常用指令

```bash
python scripts/build_stats.py && python scripts/build_known_songs.py  # 重生衍生檔
python scripts/build_song_meta.py --validate                          # 驗證 song_meta
python -m pytest scripts/tests/ -q                                    # 測試
npx astro build                                                       # 建置
./scripts/admin.sh                                                    # 本機資料編輯 GUI
```
