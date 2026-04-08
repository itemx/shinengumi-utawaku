/**
 * YouTube URL 解析 (client-side)。
 */

const VIDEO_ID_RE = /^[a-zA-Z0-9_-]{11}$/;

export function parseYouTubeUrl(input: string): { videoId: string } | null {
  const text = input.trim();
  if (!text) return null;

  // youtu.be/VIDEO_ID
  let m = text.match(/youtu\.be\/([a-zA-Z0-9_-]{11})/);
  if (m) return { videoId: m[1] };

  // youtube.com/watch?v=VIDEO_ID
  m = text.match(/[?&]v=([a-zA-Z0-9_-]{11})/);
  if (m) return { videoId: m[1] };

  // youtube.com/live/VIDEO_ID
  m = text.match(/\/live\/([a-zA-Z0-9_-]{11})/);
  if (m) return { videoId: m[1] };

  // youtube.com/shorts/VIDEO_ID
  m = text.match(/\/shorts\/([a-zA-Z0-9_-]{11})/);
  if (m) return { videoId: m[1] };

  // Bare video ID
  if (VIDEO_ID_RE.test(text)) return { videoId: text };

  return null;
}
