/**
 * 全演唱の一覧 — build 時に生成する静的 JSON。首頁の「全演唱シャッフル」と
 * /player の曲庫はこれ 1 本で動く（HTML に埋め込むと 100KB 級に膨らむので分けてある）。
 *
 * 動画の情報は v に 1 回だけ置いて、演唱側は videoId で参照する。
 * 1 本の配信に何十曲も入るので、日付や配信タイトルを演唱ごとに持つより小さい。
 *
 * 形式:
 *   { "c": [チャンネル名...],
 *     "v": { videoId: [配信タイトル, "YYYY-MM-DD", チャンネル番号] },
 *     "s": { "曲名\t歌手": [[videoId, startSeconds], ...] },
 *     "m": { "曲名\t歌手": [durationSec, [tags...]] } }
 *
 * 1 回だけの曲も載せる。/player の「演唱」表示は全演唱を 1 行ずつ並べるので、
 * どの回にも配信タイトルと日付が要る。
 */
import type { APIRoute } from "astro";
import { getChannels, getChannelData, getSongMeta } from "../lib/data";

type Take = [string, number];

export const GET: APIRoute = () => {
  const channels = getChannels();
  const videos: Record<string, [string, string, number]> = {};
  const takes = new Map<string, Take[]>();

  channels.forEach((ch, chIdx) => {
    const data = getChannelData(ch.channelId);
    if (!data) return;
    for (const v of data.videos) {
      if (v.videoStatus === "unavailable") continue; // 再生できない動画は除外
      for (const s of v.songs) {
        if (!s.seconds || s.seconds <= 0) continue; // 0:00 は単曲投稿なので代表と同じ
        const key = `${s.title}\t${s.artist}`;
        const list = takes.get(key);
        if (list) list.push([v.videoId, s.seconds]);
        else takes.set(key, [[v.videoId, s.seconds]]);
        videos[v.videoId] = [v.title, v.publishedAt.slice(0, 10), chIdx];
      }
    }
  });

  const meta = getSongMeta();
  const songs: Record<string, Take[]> = {};
  const m: Record<string, [number, string[]]> = {};
  for (const [key, list] of takes) {
    const sm = meta.get(key);
    m[key] = [sm?.durationSec ?? 0, sm?.tags ?? []];
    list.sort((a, b) => {
      const da = videos[a[0]][1], db = videos[b[0]][1];
      return da < db ? -1 : da > db ? 1 : a[1] - b[1];   // 古い順
    });
    songs[key] = list;
  }

  return new Response(
    JSON.stringify({ c: channels.map((c) => c.name), v: videos, s: songs, m }),
    { headers: { "Content-Type": "application/json" } }
  );
};
