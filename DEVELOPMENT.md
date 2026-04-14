# SEG-V UtaList - Development Notes

> VTuber singing stream setlist database for 深淵組 (Shinengumi).
> Live site: https://seg-uta.i3x.tw

---

## Architecture Overview

```
YouTube Data API v3
        │
        ▼
  Python CLI (fetch.py)          GitHub Issues (submit page)
        │                                │
        ▼                                ▼
  comment_parser.py              ingest_issue.py
  title_parser.py                        │
  normalizer.py                          │
        │                                │
        ▼                                ▼
  data/songs/{channelId}.json  ◄─────────┘
        │
        ▼
  build_stats.py + build_known_songs.py
        │
        ▼
  Astro 6.x SSG ──► GitHub Pages (seg-uta.i3x.tw)
```

Two data input paths:
1. **CLI** (`python3 scripts/fetch.py <URL>`) — bulk fetch from YouTube API
2. **Online** (`/submit` page → GitHub Issue → Action → auto-ingest)

---

## Tech Stack

| Layer | Tech | Version |
|-------|------|---------|
| SSG | Astro | 6.x |
| CSS | Tailwind CSS | 4.x via `@tailwindcss/vite` |
| Data scripts | Python | 3.12 |
| YouTube API | google-api-python-client | 2.x |
| Hosting | GitHub Pages | — |
| CI/CD | GitHub Actions | — |
| Domain/DNS | Cloudflare | seg-uta.i3x.tw |

---

## Project Structure

```
vutalist/
├── src/
│   ├── pages/
│   │   ├── index.astro           # Homepage — channel list + stats
│   │   ├── [channel].astro       # Channel page — 6 tabs (streams, covers, shorts, all songs, missing, stats)
│   │   ├── submit.astro          # Online submission form
│   │   └── song/[slug].astro     # Individual song detail
│   ├── components/
│   │   ├── PlayerBar.astro       # YouTube IFrame embedded player with channel colors
│   │   ├── LangSwitch.astro      # zh-Hant / ja switcher (cookie + localStorage + browser detect)
│   │   ├── SongTable.astro       # Song list with search + play buttons
│   │   ├── VideoCard.astro       # Stream video card
│   │   ├── CoverCard.astro       # Cover/original video card
│   │   └── StatsBar.astro        # Stats display
│   ├── layouts/Base.astro        # Base layout with header, footer, PlayerBar
│   ├── lib/
│   │   ├── data.ts               # Data reading helpers, types (VideoEntry, SongEntry)
│   │   ├── i18n.ts               # Translation dictionary (zh/ja) + t() helper
│   │   ├── slugify.ts            # URL slug: max 60 chars + 6-char djb2 hash
│   │   ├── format.ts             # Date/number formatting
│   │   ├── comment-parser.ts     # Client-side setlist parser (for submit page preview)
│   │   └── url-parser.ts         # YouTube URL parser
│   └── styles/global.css         # Tailwind 4 @theme + base layer
├── scripts/
│   ├── fetch.py                  # CLI: fetch setlists from YouTube (main entry point)
│   ├── ingest_issue.py           # Parse GitHub Issue → write to data/songs/
│   ├── build_stats.py            # Generate _stats.json + auto-clean missing list
│   ├── build_known_songs.py      # Generate known_songs.json (song→artist lookup)
│   ├── find_missing.py           # Find streams without timestamp setlists
│   └── lib/
│       ├── youtube_api.py        # YouTube Data API v3 wrapper
│       ├── comment_parser.py     # Timestamp setlist parser from comments
│       ├── title_parser.py       # Cover/original song parser from video titles
│       ├── normalizer.py         # Song/artist name normalization engine
│       ├── data_store.py         # JSON data read/write/merge helpers
│       └── url_parser.py         # YouTube URL/playlist/channel parser
├── data/
│   ├── channels.json             # Channel registry (channelId, name, colors)
│   ├── aliases.json              # Song + artist name aliases for normalization
│   ├── songs/{channelId}.json    # Per-channel song database
│   ├── missing/{channelId}.json  # Streams without setlist timestamps
│   ├── known_songs.json          # Auto-generated: unambiguous song→artist map
│   └── _stats.json               # Auto-generated: aggregate stats for Astro
├── .github/workflows/
│   ├── deploy.yml                # Build + deploy to GitHub Pages on push to main
│   └── ingest-submission.yml     # Parse Issue → ingest → commit → deploy
└── public/
    ├── CNAME                     # seg-uta.i3x.tw
    ├── favicon.svg / favicon.ico
    └── seg_nof_logo.png
```

---

## Data Flow Details

### 1. CLI Fetch (`scripts/fetch.py`)

```bash
# Fetch all videos from a channel
python3 scripts/fetch.py "https://www.youtube.com/@SuzukazeShitora"

# Fetch specific videos
python3 scripts/fetch.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

**Flow per video:**
1. YouTube API → get video info (title, duration, publishedAt)
2. Skip if upcoming/live/already ingested
3. Classify: short (≤60s) → cover → original → stream (in order)
4. For streams: fetch comments → `pick_best_comment()` → parse setlist
5. For covers/originals: parse title with `title_parser.py`
6. Normalize all song/artist names
7. Fill missing artists from `known_songs.json`
8. Dedup しとら's bilingual (JP+EN) setlists by timestamp
9. Write to `data/songs/{channelId}.json`

**Environment:** Requires `YOUTUBE_API_KEY` in `.env`

### 2. Online Submission Flow

1. User visits `/submit`, pastes YouTube URL
2. Client-side: oEmbed fetch → channel validation → type detection → setlist preview
3. User clicks submit → opens GitHub Issue with frontmatter:
   ```
   ---
   video_id: xxx
   video_title: xxx
   channel_id: UCxxx
   type: stream
   source: manual
   ---
   
   0:03:25 曲名A / 歌手A
   0:08:12 曲名B / 歌手B
   ```
4. Maintainer adds `setlist-submission` label
5. GitHub Action (`ingest-submission.yml`) triggers:
   - `ingest_issue.py` parses Issue body
   - Checks `ALLOWED_USERS` whitelist (GitHub repo variable)
   - Fetches `publishedAt` from YouTube API
   - Normalizes + writes to data
   - `build_stats.py` + `build_known_songs.py`
   - Git commit + push
   - Triggers deploy workflow
   - Closes Issue with comment

### 3. Build Pipeline

```bash
# Full build (what deploy.yml runs)
python3 scripts/build_stats.py    # Generate _stats.json, clean missing lists
python3 scripts/build_known_songs.py  # optional, for known_songs.json
npx astro build                   # SSG → dist/
```

---

## Normalization Pipeline (`scripts/lib/normalizer.py`)

Applied to every song title and artist name:

1. **NFKC** — fullwidth → halfwidth (`Ａ` → `A`, `（` → `(`)
2. **Wave dash** — `〜` (U+301C) and `～` (U+FF5E) → `~`
3. **Whitespace** — strip + collapse consecutive
4. **Quote stripping** — remove `「」『』""''`
5. **Version tags** — strip `(cover)`, `(short ver.)`, `(THE FIRST TAKE)`, `(JPN Ver.)`, `[original ver.]`, `–Piano ver.–`, `~Yui final ver.~`, etc.
6. **Title-only cleaning:**
   - TVアニメ/映画 source annotations: `(TVアニメ「xxx」OP)`, `(ウタ from ONE PIECE...)`
   - Anime prefix: `アニメ『xxx』挿入歌 曲名` → `曲名`
   - Romanization parentheses: `曲名(Romaji)` → `曲名` (only when title has Japanese chars + parens are pure Latin)
   - `feat.` stripping from title (kept in artist field)
7. **Artist-only cleaning:**
   - Romanization parentheses (same logic)
8. **Alias lookup** — `aliases.json` reverse lookup (case-insensitive)

### Comment Parser (`scripts/lib/comment_parser.py`)

- Standard timestamps: `1:03:25 曲名 / 歌手`
- Range timestamps: `0:05:30 - 0:09:10 01. 曲名` and `0:05:30 ~ 0:09:10 01. 曲名`
- Numbering stripped: `01.`, `1)`, etc.
- Skip list: スタート, エンディング, MC, はじまり, 雑談, etc.
- Talk pattern filter: regex for `の話`, `トーク`, `について`, etc.
- Song/artist separator: last `/` (rfind) — handles song names containing `/`
- `pick_best_comment()`: scores by song count × 2 + likes, channel owner bonus

### Title Parser (`scripts/lib/title_parser.py`)

Detects cover/original songs from video titles:
- Cover patterns: `【歌ってみた】`, `Covered by`, `[Cc]over`
- Original patterns: `【Original Song】`, description contains `オリジナル` (duration <10min)
- Artist extraction from hashtags (with exclusion list)

---

## Data Schema

### `data/songs/{channelId}.json`

```json
{
  "channelId": "UCxxx",
  "channelName": "Channel Name",
  "lastFetched": "2026-04-09T...",
  "videos": [
    {
      "videoId": "xxxxxxxxxxx",
      "title": "【歌枠】...",
      "publishedAt": "2025-01-15T...",
      "type": "stream",           // "stream" | "cover" | "original" | "short"
      "sourceCommentId": "Ugxxx", // or "issue#1" for submissions
      "songs": [
        {
          "timestamp": "1:03:25",
          "seconds": 3805,
          "title": "曲名",
          "artist": "歌手"
        }
      ]
    }
  ]
}
```

### `data/channels.json`

```json
[
  {
    "channelId": "UCxxx",
    "name": "Display Name",
    "keywords": ["歌枠", "singing"],
    "avatar": "https://...",
    "color": "#FCE276",          // Primary color for PlayerBar
    "colorSecondary": "#5AEBEA"  // Secondary/accent color
  }
]
```

### `data/aliases.json`

```json
{
  "songs": {
    "Canonical Title": ["alias1", "alias2"]
  },
  "artists": {
    "Canonical Artist": ["alias1", "alias2"]
  }
}
```

Lookup is case-insensitive. The canonical name is the key; all aliases (including the canonical itself) should be listed in the array.

---

## i18n System

Client-side switching between Traditional Chinese (`zh`) and Japanese (`ja`).

- **Detection priority:** cookie `vutalist-lang` → localStorage → browser language → default `ja`
- **Mechanism:** `data-i18n` attributes on elements, `data-i18n-placeholder` for inputs, `data-i18n-title` on `<html>` for page title
- **Dictionary:** `src/lib/i18n.ts` — flat key-value pairs per locale
- **Dynamic DOM:** `window.__applyI18n()` exposed for refreshing i18n on dynamically created elements

---

## PlayerBar

- Uses YouTube IFrame Player API (free, no quota)
- Channel-specific colors from `channels.json` (primary bg + secondary accent)
- Light/dark text auto-detection via `isLightColor()`
- Volume control with custom CSS range track
- Progress bar uses channel accent color
- Shuffle play: inline `allSongs` data array in channel page

---

## Adding a New Channel

1. Add entry to `data/channels.json`:
   ```json
   {
     "channelId": "UCxxx",
     "name": "Display Name",
     "keywords": ["歌枠", "singing"],
     "avatar": "https://...",
     "color": "#hex",
     "colorSecondary": "#hex"
   }
   ```

2. Fetch historical data:
   ```bash
   python3 scripts/fetch.py "https://www.youtube.com/@ChannelHandle"
   ```

3. Find missing setlists:
   ```bash
   python3 scripts/find_missing.py
   ```

4. Rebuild and deploy:
   ```bash
   python3 scripts/build_stats.py
   python3 scripts/build_known_songs.py
   npm run build
   ```

---

## GitHub Repo Settings Required

### Secrets (Settings → Secrets → Actions)
- `YOUTUBE_API_KEY` — YouTube Data API v3 key

### Variables (Settings → Variables → Actions)
- `ALLOWED_USERS` — comma-separated GitHub usernames for auto-approved submissions

### Labels
- `setlist-submission` — triggers ingest workflow
- `approved` — for non-whitelisted users (manual approval)

### Pages
- Source: GitHub Actions
- Custom domain: `seg-uta.i3x.tw`
- Enforce HTTPS: enabled

---

## Security Model

- **Submit page:** validates YouTube URL against registered channels in `channels.json`
- **Ingest workflow:** `ALLOWED_USERS` whitelist — whitelisted users auto-processed, others need `approved` label
- **Issue label injection:** `setlist-submission` label only triggers on `issues.labeled` event; adding it via Issue body doesn't trigger the workflow
- **Duplicate detection:** `merge_video()` deduplicates by `videoId`; same timestamp songs are merged, not duplicated

---

## Known Quirks & Decisions

1. **しとら bilingual dedup** — Her setlist comments often have JP + EN versions with identical timestamps. `fetch.py` deduplicates by removing entries with the same timestamp within the same video.

2. **Last separator for song/artist split** — Uses `rfind("/")` not `split("/", 1)` because song names can contain `/` (e.g., `Weight of the World / 壊レタ世界ノ歌 / 河野万里奈`).

3. **Video type classification** — Determined by YouTube API `contentDetails.duration` (≤60s = Short) + title patterns, NOT by hashtags or categories.

4. **Slug collisions** — `slugify.ts` uses max 60 chars + 6-char djb2 hash suffix to prevent both ENAMETOOLONG on GitHub Actions and slug collisions.

5. **GITHUB_TOKEN push doesn't trigger workflows** — That's why `ingest-submission.yml` explicitly calls `gh workflow run deploy.yml` after pushing data.

6. **`merge_video()` backfills** — When re-ingesting an existing video, empty `publishedAt` and `type` fields are backfilled from new data (not overwritten if already set).

7. **Wave dash** — `〜` (U+301C) is NOT converted by NFKC. Explicit replacement added in normalizer.

8. **Original song detection** — Duration <10min filter prevents matching livestreams that mention オリジナル in description (e.g., a 76-min 3D showcase).

---

## Common Operations

```bash
# Local development
npm run dev                    # Start Astro dev server

# Fetch new data
python3 scripts/fetch.py "URL" # Fetch from YouTube

# After data changes
python3 scripts/build_stats.py
python3 scripts/build_known_songs.py
npm run build                  # Full production build (includes build_stats)

# Check for normalization issues
python3 -c "
import json
from collections import defaultdict
title_artists = defaultdict(set)
for ch in ['UCSH2LgTRhPCsaVPW_emgDJg', 'UCoOPu8WqToJ4jHbBXY6NPrA']:
    with open(f'data/songs/{ch}.json') as f:
        data = json.load(f)
    for v in data['videos']:
        for s in v.get('songs', []):
            if s.get('artist'):
                title_artists[s['title']].add(s['artist'])
for t, a in sorted(title_artists.items()):
    if len(a) > 1:
        print(f'{t}: {a}')
"

# Re-normalize existing data after changing normalizer/aliases
python3 -c "
import json, sys
sys.path.insert(0, '.')
from scripts.lib.normalizer import load_aliases, normalize
aliases = load_aliases('data/aliases.json')
for ch in ['UCSH2LgTRhPCsaVPW_emgDJg', 'UCoOPu8WqToJ4jHbBXY6NPrA']:
    path = f'data/songs/{ch}.json'
    with open(path) as f:
        data = json.load(f)
    for v in data['videos']:
        for s in v.get('songs', []):
            result = normalize(s['title'], s.get('artist',''), aliases)
            s['title'] = result.title
            s['artist'] = result.artist
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
"
```

---

## Current State (v1.0 tag + subsequent fixes)

- **Channels:** 2 (涼風しとら: 146 videos / 2765 songs, 渉海よひら: 69 videos / 395 songs)
- **Known songs DB:** 1188 unique songs, 538 artists
- **All workflows verified:** submit → ingest → deploy pipeline working end-to-end
- **Data quality:** Multiple rounds of normalization completed. Remaining multi-artist entries are genuine same-name-different-song cases (Q, 再会, Across the world).
- **Submit page:** Client-side normalization (NFKC, alias lookup, feat. stripping, quote removal, wave dash) applied in preview before submission.

---

## Original Spec

See [`vtuber-setlist-plan.md`](vtuber-setlist-plan.md) for the original planning document (in Traditional Chinese) that this project was built from.
