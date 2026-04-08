/**
 * セトリ文字解析 (client-side)。
 * Python 版 comment_parser.py の輕量鏡像。
 */

export interface ParsedSong {
  timestamp: string;
  seconds: number;
  title: string;
  artist: string;
}

const TIMESTAMP_RE = /^\s*(\d{1,2}:\d{2}(?::\d{2})?)\s+(.+)$/;
const PREFIX_RE = /^(?:アンコール|encore|Encore|EN)[：:\s]+\s*/i;

const SKIP_TITLES = new Set([
  "スタート", "start", "START", "エンディング", "ending", "ENDING",
  "ED", "OP", "オープニング", "opening", "雑談", "トーク",
  "休憩", "break", "開始", "終了", "配信開始", "配信終了",
  "おまけ", "アンコール前MC",
]);

const SEPARATORS = [" / ", " ／ ", " - ", " − ", " ー "];

function timestampToSeconds(ts: string): number {
  const parts = ts.split(":").map(Number);
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  return 0;
}

function splitTitleArtist(text: string): [string, string] {
  text = text.trim();
  text = text.replace(PREFIX_RE, "").trim();

  // 「曲名」歌手
  const bracket = text.match(/[「『](.+?)[」』]\s*[/／\-]?\s*(.+)?/);
  if (bracket) return [bracket[1].trim(), (bracket[2] || "").trim()];

  // 分隔符
  for (const sep of SEPARATORS) {
    if (text.includes(sep)) {
      const [t, a] = text.split(sep, 2);
      return [t.trim(), a.trim()];
    }
  }

  // 寬鬆 /
  const loose = text.match(/(.+?)\s*[/／]\s+(.+)/);
  if (loose) return [loose[1].trim(), loose[2].trim()];

  return [text, ""];
}

export function parseSetlistText(text: string): ParsedSong[] {
  if (!text) return [];

  const lines = text.split("\n");
  const songs: ParsedSong[] = [];

  for (const line of lines) {
    const m = line.match(TIMESTAMP_RE);
    if (!m) continue;

    const ts = m[1];
    const seconds = timestampToSeconds(ts);
    if (seconds === 0) continue;

    const rest = m[2].replace(/[🎵🎶🎤🎸🎹🎼🎧♪♫★☆▶►]+/g, "").trim();
    const [title, artist] = splitTitleArtist(rest);

    if (!title || SKIP_TITLES.has(title)) continue;
    if (title.length > 40 && !artist) continue;

    songs.push({ timestamp: ts, seconds, title, artist });
  }

  return songs;
}
