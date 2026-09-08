/* PWA 用の最小 service worker。
 *
 * 方針は network-first + cache fallback。曲庫は毎日更新されるので、
 * cache-first にすると古いデータを掴んだままになる。オフライン時と
 * 通信が死んでいるときだけキャッシュを出す。
 *
 * 対象は同一オリジンの GET だけ。YouTube の iframe API や動画ストリームには
 * 一切触らない（触ると再生が壊れる）。
 */
const CACHE = "utalist-v1";
const SHELL = ["/player", "/shuffle-pool.json", "/icons/icon-192.png"];

self.addEventListener("install", (e) => {
  // 失敗しても install は通す（shell が 1 本欠けただけで PWA 全体を壊さない）
  e.waitUntil(
    caches.open(CACHE).then((c) => Promise.allSettled(SHELL.map((u) => c.add(u))))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  if (new URL(req.url).origin !== self.location.origin) return;

  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          caches.open(CACHE).then((c) => c.put(req, copy));
        }
        return res;
      })
      .catch(() => caches.match(req).then((hit) => hit || Response.error()))
  );
});
