/**
 * 同じ曲の「他の演唱」一覧 — build 時に生成する静的 JSON。
 *
 * /shuffle-pool.json は 1 曲につき代表 1 回しか持たない（首頁のシャッフルを
 * 軽くするため）。そのせいで「同じ曲の別の回」を指定することも、シャッフルで
 * 当てることもできなかった。ここで全演唱を持っておき、/player が必要に
 * なったときだけ取りに来る。
 *
 * 動画の情報は v に 1 回だけ置いて、演唱側は videoId で参照する。
 * 1 本の配信に何十曲も入るので、日付や配信タイトルを演唱ごとに持つより小さい。
 *
 * 形式:
 *   { "c": [チャンネル名...],
 *     "v": { videoId: [配信タイトル, "YYYY-MM-DD", チャンネル番号] },
 *     "s": { "曲名\t歌手": [[videoId, startSeconds], ...] } }
 *
 * 1 回だけの曲も載せる。/player の「演唱」表示は全演唱を 1 行ずつ並べるので、
 * どの回にも配信タイトルと日付が要る。
 */
import type { APIRoute } from "astro";
import { getChannels, getChannelData } from "../lib/data";

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

  const songs: Record<string, Take[]> = {};
  for (const [key, list] of takes) {
    list.sort((a, b) => {
      const da = videos[a[0]][1], db = videos[b[0]][1];
      return da < db ? -1 : da > db ? 1 : a[1] - b[1];   // 古い順
    });
    songs[key] = list;
  }

  return new Response(
    JSON.stringify({ c: channels.map((c) => c.name), v: videos, s: songs }),
    { headers: { "Content-Type": "application/json" } }
  );
};
