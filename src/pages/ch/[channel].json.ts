/**
 * チャンネルページの「開いたときに描く」中身 — build 時に生成する静的 JSON。
 *
 * 配信ごとのセトリと、全曲目の各曲の演唱一覧を HTML に全部書くと
 * 1 ページ 9 MB を超えた（ほとんどが閉じた <details> の中身）。
 * ページには見出しだけ置き、中身はこれを 1 回取ってきて開いたときに描く。
 *
 * 形式:
 *   { "v": [[videoId, 配信タイトル, "YYYY-MM-DD", [[timestamp, 秒, 曲名, 歌手], ...]], ...],
 *     "d": { "曲名\t歌手": durationSec } }   // 長さが分かっている曲だけ
 */
import type { APIRoute } from "astro";
import { getChannels, getChannelData, getSongMeta } from "../../lib/data";

export function getStaticPaths() {
  return getChannels().map((c) => ({ params: { channel: c.channelId } }));
}

export const GET: APIRoute = ({ params }) => {
  const data = getChannelData(params.channel!);
  const meta = getSongMeta();
  const d: Record<string, number> = {};
  const v = (data?.videos ?? [])
    .filter((x) => x.songs.length)
    .map((x) => [
      x.videoId,
      x.title,
      x.publishedAt.slice(0, 10),
      x.songs.map((s) => {
        const k = `${s.title}\t${s.artist}`;
        const dur = meta.get(k)?.durationSec;
        if (dur) d[k] = dur;
        return [s.timestamp, s.seconds, s.title, s.artist];
      }),
    ]);
  return new Response(JSON.stringify({ v, d }), {
    headers: { "Content-Type": "application/json" },
  });
};
