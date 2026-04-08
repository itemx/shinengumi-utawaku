/**
 * 格式化工具。
 */

/** 秒數 → hh:mm:ss 或 mm:ss */
export function formatTimestamp(seconds: number): string {
  if (!seconds || seconds <= 0) return "";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${m}:${ss}`;
}

/** 從 URL 的 ?t= 參數提取秒數 */
export function extractSeconds(url: string): number {
  try {
    const u = new URL(url);
    const t = u.searchParams.get("t");
    return t ? parseInt(t, 10) : 0;
  } catch {
    return 0;
  }
}
