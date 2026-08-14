// 使用同源相对路径：dev 由 vite proxy 转发，prod 由后端同域托管，避免跨域。
// App 封装（Capacitor 本地 WebView）时通过 VITE_API_URL 注入后端绝对地址。
export const API_URL = import.meta.env.VITE_API_URL ?? "/api";

/**
 * 把相对路径媒体 URL（如 /static/exercises/...）解析为绝对地址。
 * Web 端同源直接用相对路径即可；Capacitor App（origin=https://localhost）必须
 * 用后端绝对地址，否则图片/GIF 会解析到 localhost 而 404。
 */
export function resolveStaticUrl(url: string | null | undefined): string {
  if (!url) return "";
  if (/^https?:\/\//i.test(url)) return url;
  if (url.startsWith("/")) {
    try {
      return `${new URL(API_URL, window.location.origin).origin}${url}`;
    } catch {
      return url;
    }
  }
  return url;
}
