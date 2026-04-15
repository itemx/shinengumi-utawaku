#!/usr/bin/env python3
"""本地資料編輯 GUI。

啟動方式:
    ./scripts/admin.sh
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, jsonify, request, send_from_directory

from scripts.lib.normalizer import (
    fill_missing_artist,
    load_aliases,
    load_known_songs,
    normalize,
)

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "data"
SONGS_DIR = DATA_DIR / "songs"
ALIASES_PATH = DATA_DIR / "aliases.json"
KNOWN_PATH = DATA_DIR / "known_songs.json"
CHANNELS_PATH = DATA_DIR / "channels.json"
UI_DIR = Path(__file__).parent / "admin_ui"

app = Flask(__name__, static_folder=str(UI_DIR), static_url_path="")


def _write_json(path: Path, data) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_channels() -> dict[str, str]:
    raw = json.loads(CHANNELS_PATH.read_text(encoding="utf-8"))
    return {c["channelId"]: c["name"] for c in raw}


def _collect_songs() -> list[dict]:
    channels = _read_channels()
    rows: list[dict] = []
    for path in sorted(SONGS_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cid = data["channelId"]
        cname = channels.get(cid, cid)
        for v in data.get("videos", []):
            for i, s in enumerate(v.get("songs", [])):
                rows.append({
                    "channelId": cid,
                    "channelName": cname,
                    "videoId": v["videoId"],
                    "videoTitle": v.get("title", ""),
                    "publishedAt": v.get("publishedAt", ""),
                    "songIndex": i,
                    "timestamp": s.get("timestamp", ""),
                    "title": s.get("title", ""),
                    "titleRaw": s.get("titleRaw", ""),
                    "artist": s.get("artist", ""),
                    "artistRaw": s.get("artistRaw", ""),
                    "url": s.get("url", ""),
                })
    return rows


@app.get("/")
def index():
    return send_from_directory(UI_DIR, "index.html")


@app.get("/api/songs")
def api_songs():
    q = request.args.get("q", "").lower().strip()
    rows = _collect_songs()
    if q:
        rows = [
            r for r in rows
            if q in r["title"].lower()
            or q in r["artist"].lower()
            or q in r["titleRaw"].lower()
            or q in r["artistRaw"].lower()
            or q in r["videoId"].lower()
            or q in r["channelName"].lower()
        ]
    total = len(rows)
    return jsonify({"total": total, "rows": rows[:500]})


@app.put("/api/song")
def api_update_song():
    body = request.get_json()
    cid = body["channelId"]
    vid = body["videoId"]
    idx = body["songIndex"]
    path = SONGS_DIR / f"{cid}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for v in data["videos"]:
        if v["videoId"] == vid:
            if idx >= len(v["songs"]):
                return jsonify({"error": "index out of range"}), 400
            s = v["songs"][idx]
            for field in ("title", "artist", "titleRaw", "artistRaw"):
                if field in body:
                    s[field] = body[field]
            break
    else:
        return jsonify({"error": "video not found"}), 404
    _write_json(path, data)
    return jsonify({"ok": True})


@app.delete("/api/song")
def api_delete_song():
    body = request.get_json()
    cid = body["channelId"]
    vid = body["videoId"]
    idx = body["songIndex"]
    path = SONGS_DIR / f"{cid}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for v in data["videos"]:
        if v["videoId"] == vid:
            if idx >= len(v["songs"]):
                return jsonify({"error": "index out of range"}), 400
            del v["songs"][idx]
            break
    else:
        return jsonify({"error": "video not found"}), 404
    _write_json(path, data)
    return jsonify({"ok": True})


@app.get("/api/aliases")
def api_get_aliases():
    return jsonify(json.loads(ALIASES_PATH.read_text(encoding="utf-8")))


@app.put("/api/aliases")
def api_put_aliases():
    body = request.get_json()
    if not isinstance(body, dict) or "songs" not in body or "artists" not in body:
        return jsonify({"error": "invalid structure"}), 400
    _write_json(ALIASES_PATH, body)
    return jsonify({"ok": True})


@app.post("/api/renormalize")
def api_renormalize():
    """重跑 normalize 在所有 song 項目。"""
    aliases = load_aliases(ALIASES_PATH)
    known = load_known_songs(KNOWN_PATH)
    changed = 0
    for path in SONGS_DIR.glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        file_changed = False
        for v in data.get("videos", []):
            for s in v.get("songs", []):
                r = normalize(
                    s.get("titleRaw", ""),
                    s.get("artistRaw", ""),
                    aliases,
                )
                artist = fill_missing_artist(r.title, r.artist, known)
                if s.get("title") != r.title or s.get("artist") != artist:
                    s["title"] = r.title
                    s["artist"] = artist
                    file_changed = True
                    changed += 1
        if file_changed:
            _write_json(path, data)
    return jsonify({"changed": changed})


@app.get("/api/git/status")
def api_git_status():
    porcelain = subprocess.run(
        ["git", "status", "--porcelain", "data/"],
        cwd=ROOT, capture_output=True, text=True,
    )
    stat = subprocess.run(
        ["git", "diff", "--stat", "data/"],
        cwd=ROOT, capture_output=True, text=True,
    )
    files = [line[3:] for line in porcelain.stdout.splitlines() if line.strip()]
    return jsonify({"files": files, "stat": stat.stdout})


@app.post("/api/git/commit")
def api_git_commit():
    body = request.get_json() or {}
    message = body.get("message", "").strip()
    if not message:
        return jsonify({"error": "empty message"}), 400
    # Rebuild derived data first
    try:
        subprocess.run(
            ["python", "scripts/build_stats.py"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["python", "scripts/build_known_songs.py"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        )
    except subprocess.CalledProcessError as e:
        return jsonify({"error": f"build failed: {e.stderr}"}), 500
    subprocess.run(["git", "add", "data/"], cwd=ROOT, check=True)
    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return jsonify({"error": result.stderr or result.stdout}), 500
    return jsonify({"ok": True, "output": result.stdout})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5757)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    print(f"Admin UI: http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
