# SEG-V UtaList

VTuber singing stream setlist database for 深淵組 (Shinengumi).

Live site: [seg-uta.i3x.tw](https://seg-uta.i3x.tw)

## What This Project Is

`vutalist` is a static site and data pipeline for indexing songs sung by Shinengumi VTubers.

The project does not use a database-backed web app. Its source of truth is JSON under `data/`, generated and updated by Python scripts. Astro reads those files at build time and outputs a static site.

Core capabilities:
- Ingest singing stream setlists from YouTube comments or descriptions
- Parse cover/original uploads from video titles
- Normalize song titles and artist names
- Track per-channel song history and aggregate stats
- Accept manual submissions through `/submit` via GitHub Issues
- Periodically scan for new videos and missing setlists

## Architecture

```text
YouTube Data API v3
        |
        v
 Python scripts                GitHub Issue submissions
 (fetch / scan / build)                |
        |                              v
        +------> data/songs/*.json <---+
                    |
                    +--> data/_stats.json
                    +--> data/known_songs.json
                    +--> data/missing/*.json
                    |
                    v
              Astro static site
                    |
                    v
              GitHub Pages
```

Main ingestion paths:
- CLI fetch: `python3 scripts/fetch.py <URL>`
- Online submission: `/submit` -> GitHub Issue -> `scripts/ingest_issue.py`

## Tech Stack

- Astro 6
- Tailwind CSS 4 via `@tailwindcss/vite`
- Python 3.12
- YouTube Data API v3
- GitHub Actions
- GitHub Pages

## Current Features

Frontend:
- Homepage with channel cards and aggregate stats
- Channel pages with tabs for streams, covers, shorts, songs, missing, and stats
- Song search and appearance listing
- Bottom `PlayerBar` with YouTube IFrame playback
- `zh-Hant` / `ja` language switch
- `/submit` page with client-side parsing preview

Data pipeline:
- YouTube URL / playlist / channel parsing
- Timestamp setlist parsing from comments and descriptions
- Cover / original song parsing from titles
- Song and artist normalization with alias support
- Known-song artist autofill
- Stats generation and missing-list cleanup

Automation:
- Deploy to GitHub Pages on push to `main`
- Ingest manual submissions from labeled GitHub Issues
- Scheduled scanning for new recent videos

## Project Structure

```text
src/
  pages/
    index.astro
    [channel].astro
    submit.astro
    song/[slug].astro
  components/
    PlayerBar.astro
    SongTable.astro
    VideoCard.astro
    CoverCard.astro
    StatsBar.astro
    LangSwitch.astro
  lib/
    data.ts
    i18n.ts
    comment-parser.ts
    url-parser.ts

scripts/
  fetch.py
  scan_new.py
  ingest_issue.py
  build_stats.py
  build_known_songs.py
  find_missing.py
  lib/
    youtube_api.py
    comment_parser.py
    title_parser.py
    normalizer.py
    data_store.py
    url_parser.py

data/
  channels.json
  aliases.json
  songs/
  missing/
  known_songs.json
  _stats.json
```

## Data Model

Primary source-of-truth files:
- `data/channels.json`: registered channels and display metadata
- `data/songs/{channelId}.json`: per-channel ingested videos and songs
- `data/_stats.json`: build-time aggregate stats for Astro
- `data/known_songs.json`: unambiguous title -> artist lookup
- `data/missing/{channelId}.json`: likely singing streams still missing setlists

Each video entry generally includes:
- `videoId`
- `title`
- `publishedAt`
- `songs[]`
- `sourceCommentId`
- `type` (`stream`, `cover`, `original`, `short`)

## Local Setup

### 1. Install dependencies

```bash
npm ci
python3 -m venv .venv
./.venv/bin/pip install -r scripts/requirements.txt
./.venv/bin/pip install -r scripts/requirements-dev.txt
```

### 2. Configure environment

Create `.env` with:

```bash
YOUTUBE_API_KEY=your_api_key_here
```

### 3. Run locally

Build stats and start Astro dev server:

```bash
python3 scripts/build_stats.py
npm run dev
```

## Common Commands

Fetch a channel or video:

```bash
python3 scripts/fetch.py "https://www.youtube.com/@SuzukazeShitora"
python3 scripts/fetch.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Scan recent videos:

```bash
python3 scripts/scan_new.py --days 7
```

Rebuild generated data:

```bash
python3 scripts/build_stats.py
python3 scripts/build_known_songs.py
```

Build the site:

```bash
npm run build
```

Run tests:

```bash
PYTHONPATH=. ./.venv/bin/pytest -q
```

## GitHub Workflows

- `.github/workflows/deploy.yml`
  Builds Astro and deploys `dist/` to GitHub Pages.
- `.github/workflows/ingest-submission.yml`
  Processes issues labeled `setlist-submission`, writes data, rebuilds stats, commits, and triggers deploy.
- `.github/workflows/scan.yml`
  Periodically scans registered channels for recent videos, ingests what it can, updates missing lists, and triggers deploy if data changed.

## Notes

- `DEVELOPMENT.md` is the best high-level implementation reference in this repo.
- `task_plan.md` reflects an earlier phase plan and is not fully aligned with the current implementation state.
