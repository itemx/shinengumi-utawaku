/**
 * 隨機播放曲池 — build 時產生的靜態 JSON。
 *
 * 每首不重複曲目取一個代表演唱片段，避免把首頁塞進 100KB+ 資料；
 * 前端在按下「全部隨機播放」時才 fetch。
 *
 * 格式為精簡陣列以縮小體積：
 *   [videoId, startSeconds, title, artist, durationSec, date, channelName, tags]
 *
 * 後半 2 個是 /player 的篩選用。首頁只讀前 6 個，所以追加不影響它。
 */
import type { APIRoute } from "astro";
import { getChannels, getChannelData, getSongMeta } from "../lib/data";

type Row = [string, number, string, string, number, string, string, string[]];

export const GET: APIRoute = () => {
  const meta = getSongMeta();
  const seen = new Map<string, Row>();

  for (const ch of getChannels()) {
    const data = getChannelData(ch.channelId);
    if (!data) continue;
    for (const v of data.videos) {
      if (v.videoStatus === "unavailable") continue; // 再生できない動画は除外
      for (const s of v.songs) {
        if (!s.seconds || s.seconds <= 0) continue; // 跳過 0:00（單曲投稿/封面）
        const key = `${s.title}\t${s.artist}`;
        if (seen.has(key)) continue; // 每首歌只取第一個代表片段
        seen.set(key, [
          v.videoId,
          s.seconds,
          s.title,
          s.artist,
          meta.get(key)?.durationSec ?? 0,
          v.publishedAt.slice(0, 10),
          ch.name,
          meta.get(key)?.tags ?? [],
        ]);
      }
    }
  }

  return new Response(JSON.stringify([...seen.values()]), {
    headers: { "Content-Type": "application/json" },
  });
};
