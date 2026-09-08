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
 *
 * 代表の選び方（2026-09-08 変更）:
 *   以前は「最初に見つけた 1 件」だったが、走査順が channels.json の順なので
 *   両方が歌っている 252 曲すべてが先頭チャンネルの取り分になっていた。
 *   いまは曲名+歌手のハッシュで候補から 1 件選ぶ。build ごとに結果は同じ
 *   （決定的）だが、チャンネル順には偏らない。
 */
import type { APIRoute } from "astro";
import { getChannels, getChannelData, getSongMeta } from "../lib/data";

type Row = [string, number, string, string, number, string, string, string[]];

/** djb2。曲ごとに固定の代表を選ぶためだけのもので、暗号用途ではない */
function hash(s: string): number {
  let h = 5381;
  for (let i = 0; i < s.length; i++) h = (h * 33 + s.charCodeAt(i)) | 0;
  return h >>> 0;
}

export const GET: APIRoute = () => {
  const meta = getSongMeta();
  const candidates = new Map<string, Row[]>();

  for (const ch of getChannels()) {
    const data = getChannelData(ch.channelId);
    if (!data) continue;
    for (const v of data.videos) {
      if (v.videoStatus === "unavailable") continue; // 再生できない動画は除外
      for (const s of v.songs) {
        if (!s.seconds || s.seconds <= 0) continue; // 跳過 0:00（單曲投稿/封面）
        const key = `${s.title}\t${s.artist}`;
        const m = meta.get(key);
        const row: Row = [
          v.videoId,
          s.seconds,
          s.title,
          s.artist,
          m?.durationSec ?? 0,
          v.publishedAt.slice(0, 10),
          ch.name,
          m?.tags ?? [],
        ];
        const list = candidates.get(key);
        if (list) list.push(row);
        else candidates.set(key, [row]);
      }
    }
  }

  const out: Row[] = [];
  for (const [key, rows] of candidates) {
    out.push(rows[hash(key) % rows.length]);
  }

  return new Response(JSON.stringify(out), {
    headers: { "Content-Type": "application/json" },
  });
};
