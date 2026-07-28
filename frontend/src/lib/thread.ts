import type { Thread } from "@/types/chat";

/** 将 ISO 时间字符串格式化为「MM-DD HH:mm」便于侧边栏展示会话创建时间 */
export function formatThreadTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mi = String(d.getMinutes()).padStart(2, "0");
  return `${mm}-${dd} ${hh}:${mi}`;
}

/** 线程展示标题：自定义标题优先，回退到最后一条助手消息预览，再回退到「新对话」 */
export function threadDisplayTitle(t: Thread): string {
  return t.title || t.lastMessage || "新对话";
}
