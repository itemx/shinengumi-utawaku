# VTuber 歌枠セトリ Tracker — 開發計劃書

## 1. 專案概述

從 VTuber 歌枠（唱歌配信）的 YouTube 留言區自動擷取タイムスタンプ（時間軸），建立曲目資料庫，提供次數統計、歌手排行、時間軸直連等功能的靜態網站。

**核心價值：** 觀眾端的歌枠歷史檢索 — 「某 VTuber 唱過哪些歌、每首唱過幾次、直接跳到該段」。

---

## 2. 系統架構

```
┌─────────────────────────────────────────────────┐
│                   資料管線                        │
│                                                   │
│  npm run fetch -- --channel=UCxxxx                │
│    │                                              │
│    ├─ 1. YouTube Data API v3                      │
│    │     search.list → 列出歌枠影片               │
│    │     commentThreads.list → 抓留言             │
│    │                                              │
│    ├─ 2. 留言解析器 (comment-parser.ts)           │
│    │     篩出含 timestamp 的留言                   │
│    │     解析為 { timestamp, songTitle, artist }   │
│    │                                              │
│    ├─ 3. 曲名正規化 (normalizer.ts)               │
│    │     aliases.json 對照表                       │
│    │     半形/全形統一、大小寫統一                  │
│    │                                              │
│    └─ 4. 寫入 data/{channelId}.json               │
│                                                   │
└─────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────┐
│                  靜態建站                         │
│                                                   │
│  npm run build (Astro SSG)                        │
│    │                                              │
│    ├─ 讀取 data/*.json                            │
│    ├─ build-stats.ts 產生統計                     │
│    │   ├─ 曲別演唱次數                            │
│    │   ├─ 歌手出現次數                            │
│    │   ├─ 月份/年份趨勢                           │
│    │   └─ 跨頻道交叉統計 (Phase 2)               │
│    │                                              │
│    └─ Astro SSG → dist/ → GitHub Pages            │
│                                                   │
└─────────────────────────────────────────────────┘
```

**觸發方式：** 手動執行 CLI。無 cron、無 webhook。

---

## 3. 專案結構

```
vtuber-setlist/
├── scripts/                       # Python CLI 工具
│   ├── fetch.py                   # 主 CLI entry point (批次掃描)
│   ├── ingest_issue.py            # GitHub Action 用: 解析 Issue → merge data
│   ├── build_stats.py             # 統計產生 (Astro build 前置)
│   ├── lib/
│   │   ├── __init__.py
│   │   ├── youtube_api.py         # YouTube Data API v3 封裝
│   │   ├── comment_parser.py      # 留言/セトリ文字解析
│   │   ├── normalizer.py          # 曲名正規化
│   │   ├── url_parser.py          # YouTube URL → videoId/channelId 解析
│   │   └── data_store.py          # data/*.json 讀寫 + merge 邏輯
│   └── requirements.txt           # google-api-python-client, etc.
├── src/                           # Astro 靜態站
│   ├── lib/
│   │   ├── comment-parser.ts      # 前端用: セトリ文字解析 (submit 頁)
│   │   ├── normalizer.ts          # 前端用: alias 查表 (submit 頁)
│   │   └── url-parser.ts          # 前端用: YouTube URL 解析 (submit 頁)
│   ├── layouts/
│   │   └── Base.astro             # 共用 layout (含 PlayerBar)
│   ├── pages/
│   │   ├── index.astro            # 首頁 dashboard
│   │   ├── [channel].astro        # 單一 VTuber 頁
│   │   ├── song/[slug].astro      # 單曲統計頁
│   │   └── submit.astro           # 手動提交頁
│   ├── components/
│   │   ├── SongTable.astro        # 曲目表格 (排序/篩選)
│   │   ├── StatsCard.astro        # 統計卡片
│   │   ├── Timeline.astro         # 時間軸視圖
│   │   ├── SearchBar.astro        # 搜尋 (client-side)
│   │   ├── VideoCard.astro        # 單場配信卡片
│   │   ├── PlayerBar.astro        # 固定底部 YouTube 播放列
│   │   └── SubmitForm.astro       # 提交表單 + client-side 解析預覽
│   └── styles/
│       └── global.css
├── .github/
│   └── workflows/
│       └── ingest-submission.yml  # Issue → data commit → rebuild
├── data/
│   ├── channels.json              # 頻道設定檔
│   ├── aliases.json               # 曲名 alias 對照表
│   └── songs/
│       └── {channelId}.json       # 各頻道解析結果
├── public/
│   └── favicon.svg
├── astro.config.mjs
├── tsconfig.json
├── package.json                   # Astro + Tailwind (前端只用)
├── pyproject.toml                 # Python 專案設定 (可選, 或用 requirements.txt)
└── .env                           # YOUTUBE_API_KEY
```

### 共用邏輯的雙語策略

```
解析邏輯存在兩處:

  Python (scripts/lib/)        ← 權威版本, CLI + GitHub Action 使用
  TypeScript (src/lib/)        ← 輕量鏡像, 僅 submit 頁 client-side 預覽用

兩者共用:
  - data/aliases.json          ← 單一 source of truth
  - 相同的正則表達式和解析規則
  - 相同的正規化步驟

不一致風險管控:
  - parser 核心是正則, 邏輯簡單, 雙語維護成本低
  - submit 頁的解析只是「預覽」, 最終入庫走 GitHub Action (Python)
  - 即使前端解析略有偏差, Action 端會重新解析修正
```

---

## 4. 資料模型

> 以下 TypeScript interface 僅作為 JSON schema 描述用。
> Python 端以 dict 操作, Astro 端讀取 JSON 時可用這些型別做 type assertion。

### 4.1 channels.json — 頻道設定

```jsonc
[
  {
    "channelId": "UCxxxxxxxx",
    "name": "VTuber 名稱",
    "playlistId": "PLxxxxxxxx",   // 歌枠 playlist (可選, 比 search 精準)
    "keywords": ["歌枠", "singing", "karaoke", "歌ってみた"],  // 影片標題篩選
    "avatar": "https://..."       // 頭像 URL (手動填)
  }
]
```

### 4.2 {channelId}.json — 解析結果

```typescript
interface ChannelData {
  channelId: string;
  channelName: string;
  lastFetched: string;            // ISO8601
  videos: VideoEntry[];
}

interface VideoEntry {
  videoId: string;
  title: string;                  // 配信原始標題
  publishedAt: string;            // ISO8601
  songs: SongEntry[];
  sourceCommentId: string;        // 資料來源留言 ID (可溯源)
}

interface SongEntry {
  timestamp: string;              // 原始格式 "1:03:25" or "03:25"
  seconds: number;                // 換算秒數, 用於 ?t= 參數
  title: string;                  // 正規化後曲名
  titleRaw: string;               // 原始解析曲名
  artist: string;                 // 歌手/原唱
  artistRaw: string;              // 原始解析歌手名
  url: string;                    // https://youtu.be/{videoId}?t={seconds}
}
```

### 4.3 aliases.json — 曲名正規化對照

```jsonc
{
  "songs": {
    "夜に駆ける": ["夜に駆ける", "yoru ni kakeru", "Racing into the Night", "夜にかける"],
    "うっせぇわ": ["うっせぇわ", "usseewa", "うっせえわ"],
    "シャルル": ["シャルル", "Charles", "charles"]
  },
  "artists": {
    "YOASOBI": ["YOASOBI", "yoasobi", "Yoasobi"],
    "Ado": ["Ado", "ado", "アド"]
  }
}
```

### 4.4 build 階段產生的統計結構

```typescript
interface SongStats {
  title: string;                  // 正規化曲名
  artist: string;
  count: number;                  // 總演唱次數
  appearances: {
    videoId: string;
    channelId: string;
    date: string;
    url: string;                  // 含 timestamp 的直連
  }[];
  firstSung: string;              // 最早演唱日期
  lastSung: string;               // 最近演唱日期
}

interface ChannelStats {
  channelId: string;
  channelName: string;
  totalSongs: number;             // 總曲數 (含重複)
  uniqueSongs: number;            // 不重複曲數
  totalVideos: number;            // 歌枠場數
  topSongs: SongStats[];          // 演唱次數 Top N
  topArtists: { artist: string; count: number }[];
  monthlyActivity: { month: string; count: number }[];
}
```

---

## 5. 核心邏輯規格

### 5.1 fetch.py — CLI 主程式

```
用法:
  python scripts/fetch.py <URL|ID> [...URL|ID] [--force]

引數: 直接貼 YouTube URL 或 ID, 可混用, 可多個

  支援的 URL / ID 格式:
    頻道 (掃描該頻道所有歌枠):
      https://www.youtube.com/@ChannelHandle
      https://www.youtube.com/channel/UCxxxxxxxx
      https://youtube.com/@ChannelHandle
      UCxxxxxxxx                               (裸 channel ID)

    單一影片 (只抓該影片):
      https://www.youtube.com/watch?v=VIDEO_ID
      https://youtu.be/VIDEO_ID
      https://www.youtube.com/live/VIDEO_ID
      VIDEO_ID                                 (裸 11 字元 video ID)

    播放清單 (掃描清單內所有影片):
      https://www.youtube.com/playlist?list=PLxxxxxxxx
      PLxxxxxxxx                               (裸 playlist ID)

  旗標:
    --force     強制重新抓取已存在的影片 (預設跳過)

  實作: argparse, positional nargs="+", --force store_true

URL 解析邏輯 (scripts/lib/url_parser.py):
  輸入: str
  輸出: UrlParseResult(type='channel'|'video'|'playlist', id=str)

  解析規則:
    1. urllib.parse.urlparse, 依 hostname + path + query 判斷類型
    2. 若非合法 URL → 依長度/前綴判斷:
       - 以 "UC" 開頭, 24 chars → channel
       - 以 "PL" 開頭 → playlist
       - 11 chars, re.match(r'^[a-zA-Z0-9_-]{11}$') → video
       - 以 "@" 開頭 → channel handle (需 API resolve)
    3. handle → channelId 轉換:
       channels.list(forHandle=@xxx) → channelId
       (消耗 1 unit, 只在首次需要, 結果寫入 channels.json 快取)

流程:
  1. 逐引數呼叫 url_parser.parse(), 分類為 channels / videos / playlists
  2. playlist → playlistItems.list 展開為 video list
  3. channel:
     a. 查 channels.json 是否已註冊
     b. 未註冊 → 用 channels.list 取得名稱, 自動新增到 channels.json
     c. 列出歌枠影片 (playlistId 或 search + keywords)
  4. 合併所有待處理的 videoId list
  5. 過濾掉已抓取的 videoId (除非 --force)
  6. 逐影片: commentThreads.list → comment_parser → normalizer
  7. Merge 進對應的 data/songs/{channelId}.json
  8. stdout 輸出摘要: 新增 N 部影片, M 首歌

  單一影片的 channelId 解析:
    - videos.list(id=VIDEO_ID, part='snippet') → snippet['channelId']
    - 1 unit, 也順便取得 title, publishedAt
```

### 5.2 comment_parser.py — 留言解析

```
輸入: comment_text: str
輸出: list[SongEntry] | None

解析策略 (依優先序):

  1. 結構化セトリ格式:
     偵測含有 3 行以上 timestamp 的留言
     每行格式: {timestamp} {songTitle} [/ {artist}]

  2. Timestamp 正則:
     r'^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$'  (re.MULTILINE)

  3. 曲名/歌手分離:
     嘗試以下分隔符 (依序):
       " / "  " ／ "  " - "  " ー "  "「」內為曲名"
     若無分隔符 → artist 設為空字串, 後續手動補

  4. 選擇最佳留言:
     同一影片可能有多則 timestamp 留言
     評分標準:
       - 解析出的曲數 (越多越好, 代表越完整)
       - 留言按讚數 (likeCount)
       - 是否為頻道擁有者留言 (authorChannelId == channelId)
     取最高分的一則

邊界處理:
  - 忽略純聊天 timestamp (如 "5:23 ここ草")
    → 檢查: 同一留言中 timestamp 行數 >= 3 才視為セトリ
  - 忽略 timestamp 為 0:00 的行 (通常是配信開始標記)
  - 處理帶有 emoji 或裝飾符號的行: 先 strip 再解析
  - 留言中的 "#" 標籤行跳過
```

### 5.3 normalizer.py — 曲名正規化

```
輸入: title_raw: str, artist_raw: str
輸出: NormalizeResult(title=str, artist=str, matched=bool)

步驟:
  1. 基礎清理:
     - str.strip()
     - unicodedata.normalize('NFKC') → 全形英數自動轉半形
     - re.sub(r'\s+', ' ', text) → 連續空白合一
     - 移除前後的引號/括號裝飾: 「」『』""
     - 移除尾部的 (cover), (カバー), (short ver.) 等標註

  2. Alias 查表:
     - json.load(aliases.json)
     - 對 title 和 artist 分別查表
     - 查表用 .lower() 比對, 輸出用 canonical form
     - aliases 建成 reverse lookup dict (啟動時一次性):
         {"夜にかける": "夜に駆ける", "yoru ni kakeru": "夜に駆ける", ...}

  3. 未命中處理:
     - 若 alias 未命中 → matched=False, 保留清理後的原始值
     - 呼叫端決定是否寫入 data/unmatched.log
```

### 5.4 build_stats.py — 統計產生

```
觸發: package.json "prebuild" script → python scripts/build_stats.py
輸入: data/songs/*.json
輸出: data/_stats.json (供 Astro 頁面讀取)

統計項目:
  Per channel:
    - uniqueSongs, totalSongs, totalVideos
    - topSongs (by count, top 50)
    - topArtists (by count, top 30)
    - monthlyActivity (每月歌枠場數 + 曲數)
    - recentVideos (最近 10 場)

  Global (跨頻道, Phase 2):
    - 所有頻道共通曲目
    - 全域曲目排行
    - 全域歌手排行

實作: collections.Counter + pathlib.glob + json.dump
```

---

## 6. 前端頁面規格

### 技術棧

- **框架:** Astro 5.x (SSG mode, output: 'static')
- **樣式:** Tailwind CSS 4.x (Vite plugin)
- **互動:** 少量 client-side JS (搜尋篩選 + YouTube 播放器控制), 無框架依賴
- **播放器:** YouTube IFrame Player API (嵌入式播放, 無需跳轉)
- **部署:** GitHub Pages (`astro.config.mjs` → `site`, `base` 設定)
- **字體:** Noto Sans JP (本文) + 特色 display font (標題)

### 6.1 首頁 index.astro

```
路由: /
內容:
  - 網站標題 + 簡介
  - 頻道卡片列表 (各 VTuber)
    - 頭像, 名稱
    - 歌枠場數, 不重複曲數
    - 最近一場日期
    - → 點擊進入 /[channel]
  - (Phase 2) 全域統計摘要
```

### 6.2 頻道頁 [channel].astro

```
路由: /{channelId}
內容:
  Header:
    - VTuber 名稱 + 頭像
    - 統計概覽: 歌枠場數 / 總曲數 / 不重複曲數

  Tab 1 — 曲目一覽 (預設):
    - 可搜尋的表格
    - 欄位: 曲名 | 歌手 | 演唱次數 | 最近日期
    - 點擊次數 → 展開所有演唱紀錄 (含直連)
    - 排序: 次數↓, 曲名, 歌手, 日期
    - 搜尋: client-side filter (曲名 + 歌手)

  Tab 2 — 歌枠列表:
    - 以配信為單位的時間軸
    - 各場顯示: 日期 | 配信標題 | 曲數
    - 展開 → 該場セトリ + 每曲 timestamp 直連

  Tab 3 — 統計:
    - Top 20 歌曲 bar chart (純 CSS 或 SVG)
    - Top 10 歌手 bar chart
    - 月份活動量折線 (場數 + 曲數)
```

### 6.3 單曲頁 song/[slug].astro

```
路由: /song/{slug}
slug 產生: slugify(title + "__" + artist)
內容:
  - 曲名 + 歌手
  - 總演唱次數
  - 所有演唱紀錄:
    - 日期 | VTuber | 配信標題 | ▶ 直連
  - (Phase 2) 跨頻道統計: 哪些 VTuber 唱過這首
```

### 6.4 PlayerBar 元件 — 固定底部播放列

```
位置: Base.astro layout 底部, position: fixed, bottom: 0
狀態: 預設隱藏, 首次點擊播放後滑入

┌────────────────────────────────────────────────────────┐
│ ▶/⏸  ◀ ▶  夜に駆ける / YOASOBI   [━━━━━━━●━━━] 2:31  │
│          2024/03/15 歌枠 #42                     ✕ 關閉 │
└────────────────────────────────────────────────────────┘
   ↑         ↑              ↑            ↑          ↑
 播放/暫停  上下首    曲名/歌手     進度條    關閉播放列

實作:
  HTML:
    - 外層 div#player-bar, 初始 class="hidden"
    - 內含隱藏的 div#yt-player (YouTube iframe 掛載點)
    - 控制列: 播放鈕, 上下首, 曲資訊, 進度條, 關閉鈕

  YouTube IFrame Player API 載入:
    - Base.astro 載入 <script src="https://www.youtube.com/iframe_api">
    - onYouTubeIframeAPIReady callback 初始化 player instance
    - player 設定:
        height: 0, width: 0         // 隱藏 iframe 本體
        playerVars:
          autoplay: 1
          controls: 0               // 用自製 UI
          disablekb: 1
          modestbranding: 1
          rel: 0

  播放觸發 (data-play 屬性):
    - 所有播放連結統一用 <a> 標籤:
        <a href="https://youtu.be/{videoId}?t={seconds}"
           data-play
           data-video-id="{videoId}"
           data-start="{seconds}"
           data-title="{songTitle}"
           data-artist="{artist}"
           data-date="{publishedAt}">
          ▶ {songTitle}
        </a>
    - 全域 click delegate:
        document.addEventListener('click', (e) => {
          const link = e.target.closest('[data-play]');
          if (!link) return;
          e.preventDefault();
          playTrack({
            videoId: link.dataset.videoId,
            start: parseInt(link.dataset.start),
            title: link.dataset.title,
            artist: link.dataset.artist,
            date: link.dataset.date
          });
        });

  playTrack() 邏輯:
    1. player.loadVideoById({ videoId, startSeconds })
    2. 更新曲資訊顯示 (title, artist, date)
    3. 更新 currentIndex (用於上下首)
    4. player-bar 移除 hidden class, 加入 slide-up 動畫
    5. 頁面 body 加 padding-bottom 避免內容被遮蔽

  上下首邏輯:
    - 維護 playlist: SongEntry[] (當前頁面可見的播放列表)
    - 進入頻道頁 → playlist = 該頻道所有 songs (按日期排序)
    - 進入單曲頁 → playlist = 該曲所有演唱紀錄
    - 展開某場セトリ → playlist = 該場所有曲目
    - ◀ ▶ 按鈕在 playlist 內切換 currentIndex

  進度條:
    - player.getCurrentTime() / player.getDuration()
    - setInterval 每秒更新
    - 可拖動: 點擊/拖動時呼叫 player.seekTo()

  播放結束:
    - onStateChange → YT.PlayerState.ENDED
    - 自動播下一首 (若 playlist 有下一曲)

  關閉:
    - player.stopVideo()
    - player-bar 加 hidden
    - body padding-bottom 移除

  Fallback:
    - <a href> 保留原始 YouTube 連結
    - JS 未載入或 API 失敗時, 連結正常跳轉到 YouTube
    - Progressive enhancement, 不依賴 JS 也能用
```

### 6.5 播放列互動與頁面整合

```
頁面內容區需配合 PlayerBar 的調整:

  body:
    - PlayerBar 可見時: padding-bottom: var(--player-height, 72px)
    - transition: padding-bottom 0.3s

  所有 timestamp 直連統一改用 data-play 屬性:
    - SongTable.astro: 展開的演唱紀錄列
    - Timeline.astro: セトリ內各曲
    - VideoCard.astro: 該場セトリ各曲
    - song/[slug].astro: 所有演唱紀錄

  Playlist context 傳遞:
    - 各元件在渲染播放連結時, 同時將該 context 的 song list
      寫入一個隱藏的 <script type="application/json" data-playlist>
    - PlayerBar JS 在 playTrack 時讀取最近的 data-playlist
      作為上下首切換的範圍
```

### 6.6 手動提交頁 submit.astro

```
路由: /submit
用途: 任何人 (包含站長自己) 快速新增一場歌枠的セトリ

┌──────────────────────────────────────────────────────┐
│  新增歌枠セトリ                                        │
│                                                        │
│  YouTube URL:                                          │
│  ┌──────────────────────────────────────────────────┐ │
│  │ https://www.youtube.com/watch?v=xxxxxxxxxx       │ │
│  └──────────────────────────────────────────────────┘ │
│  → 自動解析: videoId, 用 oEmbed 取得影片標題 + 縮圖    │
│                                                        │
│  セトリ (每行一曲):                                     │
│  ┌──────────────────────────────────────────────────┐ │
│  │ 00:03:25 夜に駆ける / YOASOBI                    │ │
│  │ 00:08:12 うっせぇわ / Ado                         │ │
│  │ 00:15:40 シャルル / バルーン                       │ │
│  │                                                    │ │
│  └──────────────────────────────────────────────────┘ │
│                                                        │
│  頻道:  [▼ 下拉選單: channels.json 的已註冊頻道]       │
│         [ ] 新頻道 (手動輸入 channelId)                 │
│                                                        │
│  ┌──────────┐                                         │
│  │  預覽解析  │                                        │
│  └──────────┘                                         │
│                                                        │
│  ─── 預覽區 ──────────────────────────────────────── │
│  影片: 【xxxxxxxx】配信標題 (from oEmbed)              │
│  解析結果: 3 曲                                        │
│  ┌────────┬─────────────────┬──────────┬──────────┐ │
│  │ 時間    │ 曲名             │ 歌手      │ 狀態     │ │
│  ├────────┼─────────────────┼──────────┼──────────┤ │
│  │ 3:25   │ 夜に駆ける       │ YOASOBI  │ ✓ 已正規 │ │
│  │ 8:12   │ うっせぇわ        │ Ado      │ ✓ 已正規 │ │
│  │ 15:40  │ シャルル          │ バルーン  │ ⚠ 未登錄 │ │
│  └────────┴─────────────────┴──────────┴──────────┘ │
│  ⚠ 1 曲未在 aliases.json 中, 將以原始名稱登錄          │
│                                                        │
│  ┌──────────────────┐                                 │
│  │  提交 (建立 Issue) │                                │
│  └──────────────────┘                                 │
└──────────────────────────────────────────────────────┘

實作細節:

  URL 解析 (client-side):
    - 支援格式:
        https://www.youtube.com/watch?v=VIDEO_ID
        https://youtu.be/VIDEO_ID
        https://www.youtube.com/live/VIDEO_ID
        https://youtube.com/watch?v=VIDEO_ID&t=123
    - 正則: /(?:v=|youtu\.be\/|\/live\/)([a-zA-Z0-9_-]{11})/
    - 取出 videoId 後, 呼叫 oEmbed (無需 API key):
        fetch(`https://www.youtube.com/oembed?url=https://youtu.be/${videoId}&format=json`)
        → 取得 title, author_name, thumbnail_url

  セトリ文字解析:
    - 複用 comment-parser 的解析邏輯
    - 但在 client-side 執行, 需將 parser 抽成可在瀏覽器跑的 pure function
    - 解析後對照 aliases.json (build 時 inline 進頁面的 JSON)
    - 顯示正規化狀態: ✓ 已正規 / ⚠ 未登錄

  提交機制 — GitHub Issue (零 backend):
    - 點擊「提交」→ 組成 Issue body → window.open() 開 GitHub Issue 建立頁
    - URL 格式:
        https://github.com/{owner}/{repo}/issues/new?
          labels=setlist-submission&
          title=[セトリ] {videoTitle}&
          body={encodedBody}

    - Issue body 格式 (結構化, 方便 Action 解析):
        ```
        ---
        video_id: dQw4w9WgXcQ
        channel_id: UCxxxxxxxx
        video_title: 配信標題
        published_at: 2024-03-15T19:00:00Z
        source: manual
        ---

        00:03:25 夜に駆ける / YOASOBI
        00:08:12 うっせぇわ / Ado
        00:15:40 シャルル / バルーン
        ```

    - 需要 GitHub 帳號才能建 Issue (自然的 spam 防護)
    - 站長自己用也是同一流程, 統一入口
```

### 6.7 提交處理管線 — GitHub Action

```
觸發: issues.labeled (label = "setlist-submission")

Workflow: .github/workflows/ingest-submission.yml

  on:
    issues:
      types: [labeled]

  jobs:
    ingest:
      if: contains(github.event.issue.labels.*.name, 'setlist-submission')
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v4
        - uses: actions/setup-python@v5
          with: { python-version: '3.12' }
        - run: pip install -r scripts/requirements.txt

        - name: Parse and ingest
          run: python scripts/ingest_issue.py ${{ github.event.issue.number }}
          env:
            GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

        - name: Commit data
          run: |
            git config user.name "github-actions[bot]"
            git config user.email "github-actions[bot]@users.noreply.github.com"
            git add data/
            git diff --cached --quiet || git commit -m "ingest: #${{ github.event.issue.number }}"
            git push

        - name: Close issue
          run: gh issue close ${{ github.event.issue.number }} --comment "已入庫 ✓"
          env:
            GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}

        - name: Trigger rebuild
          # push to main 已自動觸發 GitHub Pages build
          # 若用獨立 deploy workflow, 在此 dispatch

scripts/ingest_issue.py 邏輯:
  1. requests + GITHUB_TOKEN 讀取 Issue body
  2. 解析 frontmatter (--- 區塊) → video_id, channel_id, etc. (pyyaml 或手動 split)
  3. 解析 body 的 timestamp 行 (from lib.comment_parser import parse)
  4. 正規化 (from lib.normalizer import normalize)
  5. 讀取 data/songs/{channelId}.json
  6. 檢查 videoId 是否已存在:
     - 已存在 → merge (新增缺少的曲目, 不覆蓋既有)
     - 不存在 → append 新 video entry
  7. 更新 lastFetched timestamp
  8. 寫回 JSON (json.dump, ensure_ascii=False, indent=2)
  9. 若有未匹配的曲名 → append 到 data/unmatched.log
```

### 6.8 兩條資料路徑對照

```
                    ┌─────────────────┐
                    │   data/*.json   │
                    └────────▲────────┘
                             │
              ┌──────────────┼──────────────┐
              │                             │
    ┌─────────┴──────────┐     ┌────────────┴───────────┐
    │  路徑 A: 批次掃描   │     │  路徑 B: 手動提交       │
    │                     │     │                         │
    │  python fetch.py    │     │  /submit 頁面           │
    │  <URL>              │     │    ↓                    │
    │    ↓                │     │  GitHub Issue           │
    │  YouTube API        │     │    ↓                    │
    │  留言區/描述欄      │     │  GitHub Action          │
    │    ↓                │     │  ingest_issue.py        │
    │  comment_parser     │     │    ↓                    │
    │  normalizer         │     │  comment_parser         │
    │    ↓                │     │  normalizer             │
    │  寫入 JSON          │     │    ↓                    │
    │                     │     │  commit + push          │
    └─────────────────────┘     └─────────────────────────┘

兩條路徑共用:
  - comment_parser.py (同一份解析邏輯, Python 為權威版本)
  - normalizer.py (同一份正規化)
  - data schema (同一份 JSON 結構)
  - merge 策略 (videoId 去重, song 層級 merge)
  - aliases.json (單一 source of truth)
```

---

## 7. YouTube API 用量估算

```
前提: 每日 quota 10,000 units (免費)

操作                        Units/call   每次回傳
search.list                 100          50 筆
playlistItems.list          1            50 筆
commentThreads.list         1            100 筆
channels.list (handle解析)  1            1 筆     ← 新增, 首次 @handle → channelId
videos.list (單影片 meta)   1            1 筆     ← 新增, 貼影片 URL 時取 channelId + title

範例 A: 1 頻道 URL, 50 部歌枠影片
  channels.list (handle→id): 1 unit × 1 = 1
  search.list: 100 units × 1 call = 100
  commentThreads.list: 1 unit × 50 calls = 50
  合計: 151 units

範例 B: 直接貼 5 部影片 URL
  videos.list: 1 unit × 5 = 5
  commentThreads.list: 1 unit × 5 = 5
  合計: 10 units → 極低

結論: 手動觸發下, 即使一次抓 5 個頻道各 100 部影片也完全夠用
```

---

## 8. 開發階段

### Phase 1 — 單一頻道 MVP

1. 專案初始化: Astro + Tailwind (前端) / Python venv + requirements.txt (scripts)
2. scripts/lib/youtube_api.py — API 封裝 (google-api-python-client)
3. scripts/lib/url_parser.py — URL 解析 + pytest 測試
4. scripts/lib/comment_parser.py — 留言解析 + pytest 測試
5. scripts/lib/normalizer.py — 正規化 + aliases.json 初始資料
6. scripts/lib/data_store.py — JSON 讀寫 + merge 邏輯
7. scripts/fetch.py — CLI 整合 (批次掃描路徑)
8. 用 1 個真實頻道跑一輪, 驗證 data output
9. scripts/build_stats.py — 統計產生
10. src/lib/*.ts — 前端用 parser/normalizer 輕量鏡像
11. Astro 頁面: index + [channel] + song/[slug]
12. PlayerBar.astro — 固定底部播放列 + YouTube IFrame API 整合
13. 各頁面播放連結統一掛載 data-play 屬性 + playlist context
14. submit.astro + SubmitForm.astro — 手動提交頁
15. .github/workflows/ingest-submission.yml + scripts/ingest_issue.py
16. GitHub Pages 部署設定
17. README 撰寫

### Phase 2 — 多頻道 + 交叉統計

1. channels.json 擴充多頻道
2. 全域統計頁
3. 跨頻道單曲頁 (同一首歌被哪些人唱過)
4. aliases.json 擴充
5. submit 頁面支援新頻道登錄 (Issue 含新頻道 metadata)

### Phase 3 — 品質提升 (Optional)

1. 留言解析 LLM fallback (格式不標準時用 OpenAI 解析)
2. fuzzy match 曲名 (rapidfuzz / thefuzz)
3. 配信縮圖顯示
4. RSS/Atom feed (新歌枠通知)
5. i18n (中文/日文/英文)
6. submit 頁面: 批次提交 (多個 URL 一次貼)

---

## 9. 環境需求

```
Python >= 3.11
Node.js >= 20 (僅 Astro 前端建站用)
pnpm (偏好) 或 npm
YouTube Data API v3 key (Google Cloud Console)
```

### scripts/requirements.txt

```
google-api-python-client>=2.100
python-dotenv>=1.0
requests>=2.31
```

### .env

```
YOUTUBE_API_KEY=your_api_key_here
```

---

## 10. CLI 使用範例

```bash
# 掃描頻道所有歌枠 — 直接貼頻道頁 URL
python scripts/fetch.py https://www.youtube.com/@KanataChannel

# 同上, 用 channel ID 也行
python scripts/fetch.py UCxxxxxxxx

# 抓單一影片 — 直接貼影片 URL
python scripts/fetch.py https://www.youtube.com/watch?v=dQw4w9WgXcQ

# 抓整個播放清單
python scripts/fetch.py https://www.youtube.com/playlist?list=PLxxxxxxxx

# 混合使用: 掃一個頻道 + 補一部單獨影片
python scripts/fetch.py https://www.youtube.com/@SuiseiChannel https://youtu.be/abcdefg1234

# 強制重抓已存在的影片
python scripts/fetch.py https://youtu.be/dQw4w9WgXcQ --force

# 產生統計 (通常不需手動跑, npm run build 會自動觸發)
python scripts/build_stats.py

# 建站 (自動先跑 build_stats.py)
npm run build

# 本地預覽
npm run dev
```

---

## 11. 注意事項與風險

| 風險 | 對策 |
|---|---|
| 留言區無セトリ | fallback: 影片描述欄也常有 timestamp, parser 同時檢查 description |
| セトリ格式混亂 | 評分機制選最佳留言; unmatched.log 人工介入 |
| 非公開/刪除影片 | fetch 時 graceful skip, 保留已抓取的歷史資料 |
| 曲名寫法混亂 | aliases.json 持續擴充; Phase 3 加 fuzzy match |
| API quota 超限 | 手動觸發 + 增量抓取, 實務上不會超 |
| 歌枠被標記為會限/刪除 | 已抓取的資料保留在 JSON, 不受影片狀態影響 |
| 嵌入播放被限制 | 部分影片禁止嵌入 (embeddable=false); player onError 時 fallback 開新分頁到 YouTube |
| 會限影片無法嵌入 | player onError code 150 → 顯示「此影片需登入 YouTube 觀看」+ 原始連結 |
| 行動裝置 autoplay 限制 | iOS/Android 禁止自動播放有聲影片; 首次需用戶互動觸發, 之後切歌正常 |
| Issue body URL 長度限制 | GitHub new issue URL 上限 ~8000 chars; 超長セトリ改用 body 預填 textarea (不用 query param) |
| 手動提交 spam/惡意資料 | 需 GitHub 帳號 = 自然防護; Issue label 可加人工審核流程 (改 labeled → 手動加 label) |
| 重複提交同一影片 | ingest-issue.ts merge 時以 videoId 去重; 同場新增曲目, 不覆蓋既有 |
