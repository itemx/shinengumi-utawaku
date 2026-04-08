/**
 * 將曲名+歌手轉為 URL-safe slug。
 * 用短 hash 避免衝突和過長路徑。
 */
export function slugify(title: string, artist: string): string {
  const raw = `${title}__${artist}`;
  const base = raw
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);

  // 簡易 hash (djb2) 避免衝突
  let hash = 5381;
  for (let i = 0; i < raw.length; i++) {
    hash = ((hash << 5) + hash + raw.charCodeAt(i)) & 0x7fffffff;
  }
  const suffix = hash.toString(36).slice(0, 6);

  return `${base}-${suffix}`;
}
