/**
 * 將曲名+歌手轉為 URL-safe slug。
 */
export function slugify(title: string, artist: string): string {
  const raw = `${title}__${artist}`;
  return raw
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 120);
}
