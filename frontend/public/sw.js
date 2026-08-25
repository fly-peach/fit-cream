/*
 * Service Worker 退役脚本（一次性）
 *
 * 背景：早期构建曾注册过 Service Worker；当前构建不再使用 PWA/SW。
 * 但旧浏览器中残留的 SW 仍会拦截请求（曾导致 /api 请求被吞、登录失效）。
 * 本脚本作为 /sw.js 提供后，浏览器更新检查会安装它，activate 时立即：
 *   1. 删除本 origin 全部 CacheStorage 缓存
 *   2. 注销本 Service Worker 自身
 * 之后该站点不再有任何 SW，请求全部直连服务器。
 */
self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      try {
        const keys = await caches.keys();
        await Promise.all(keys.map((k) => caches.delete(k)));
      } catch (e) {
        console.error("[sw] cache clear failed", e);
      }
      try {
        if (self.registration) {
          await self.registration.unregister();
        }
      } catch (e) {
        console.error("[sw] unregister failed", e);
      }
    })()
  );
  self.clients.claim();
});
