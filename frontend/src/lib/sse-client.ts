import type { SSEEvent } from "@/types/chat";

// 使用同源相对路径：dev 由 vite proxy 转发，prod 由后端同域托管，避免跨域
const API_URL = "/api";

export async function* streamChat(
  message: string,
  threadId: string | null,
  signal?: AbortSignal,
  token?: string
): AsyncGenerator<SSEEvent> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_URL}/chat/message`, {
    method: "POST",
    headers,
    body: JSON.stringify({ message, thread_id: threadId }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() || "";

    let eventType = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        eventType = line.slice(7).trim();
      } else if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.slice(6));
          yield { event: eventType as SSEEvent["event"], data };
        } catch {
          // skip malformed JSON
        }
      }
    }
  }
}

export async function stopGeneration(threadId: string, token?: string): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  await fetch(`${API_URL}/chat/stop`, {
    method: "POST",
    headers,
    body: JSON.stringify({ thread_id: threadId }),
  });
}
