"""缺歌手的歌單 → 開 GitHub Issue 待人工補完。

scan_new 抓到歌單但有曲目缺歌手時，不自動入庫，改開一個 review issue
(不帶 setlist-submission label，所以不會觸發自動 ingest)。使用者補齊歌手後
自行加上 setlist-submission label，即走現有 ingest 流程入庫。
"""

from __future__ import annotations

import os

import requests


def build_issue_body(
    video_id: str, video_title: str, channel_id: str,
    song_entries: list[dict],
) -> str:
    """組出 review issue 內容 (submit 格式，可被 ingest_issue 解析)。

    缺歌手的行只有「timestamp 曲名」，補齊時在後面加「 / 歌手」。
    """
    missing = [s["title"] for s in song_entries if not s.get("artist")]
    note_lines = [
        "> ⚠️ 自動掃描發現這場歌枠有曲目缺歌手，未自動入庫。",
        "> 請在下方 setlist 補上缺少的 `/ 歌手`，確認無誤後把本 issue 加上",
        "> `setlist-submission` label 即會自動入庫。",
    ]
    if missing:
        note_lines.append("> 缺歌手：" + "、".join(missing))
    note = "\n".join(note_lines)

    setlist = "\n".join(
        s["timestamp"] + " " + s["title"] + (" / " + s["artist"] if s.get("artist") else "")
        for s in song_entries
    )

    return (
        note + "\n\n"
        "---\n"
        f"video_id: {video_id}\n"
        f"video_title: {video_title}\n"
        f"channel_id: {channel_id}\n"
        "type: stream\n"
        "source: scan-review\n"
        "---\n\n"
        + setlist
    )


def create_review_issue(
    video_id: str, video_title: str, channel_id: str,
    song_entries: list[dict],
) -> bool:
    """透過 GitHub API 開 review issue。

    需要環境變數 GITHUB_TOKEN 與 GITHUB_REPOSITORY。
    回傳 True 表示成功建立 (或 dry-run 印出)，False 表示缺 token 無法建立。
    """
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    body = build_issue_body(video_id, video_title, channel_id, song_entries)
    title = f"[要補歌手] {video_title}"

    if not repo or not token:
        print("      ⚠ 無 GITHUB_TOKEN/REPOSITORY，跳過開 issue (dry-run)")
        return False

    resp = requests.post(
        f"https://api.github.com/repos/{repo}/issues",
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        json={"title": title, "body": body},
        timeout=30,
    )
    if resp.status_code == 201:
        print(f"      🎫 開 review issue #{resp.json().get('number')}")
        return True
    print(f"      ⚠ 開 issue 失敗 ({resp.status_code}): {resp.text[:120]}")
    return False


if __name__ == "__main__":
    # body 組裝自我檢查
    entries = [
        {"timestamp": "0:09", "title": "鯨が落ちる街", "artist": ""},
        {"timestamp": "0:12", "title": "雨景色", "artist": "ロクデナシ"},
    ]
    b = build_issue_body("vid1", "テスト歌枠", "UCxxxx", entries)
    assert "setlist-submission" in b
    assert "缺歌手：鯨が落ちる街" in b
    assert "0:09 鯨が落ちる街\n" in b or b.endswith("0:09 鯨が落ちる街")
    assert "0:12 雨景色 / ロクデナシ" in b
    # frontmatter 可被 split("---", 2) 正確切出
    parts = b.split("---", 2)
    assert len(parts) == 3 and "video_id: vid1" in parts[1]
    print("OK")
