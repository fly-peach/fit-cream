import type { SSEEvent } from "@/types/chat";
import { API_URL, checkAuthEnvelope, isAuthError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

export async function* streamChat(
  message: string,
  threadId: string | null,
  signal?: AbortSignal,
  images?: string[],
  planDesign?: boolean
): AsyncGenerator<SSEEvent> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  const body: Record<string, unknown> = { message, thread_id: threadId };
  if (images && images.length > 0) body.images = images;
  if (planDesign) body.plan_design = true;

  const response = await fetch(`${API_URL}/chat/message`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    signal,
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  // 认证失败时后端在依赖校验阶段即返回 HTTP 200 + JSON 信封（非事件流），
  // 需识别 401xx 业务码并自动登出，否则流解析会得到空结果而静默失败。
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("text/event-stream")) {
    let envelope: { code?: number; message?: string } = {};
    try {
      envelope = await response.json();
    } catch {
      // 非 JSON 响应，忽略解析
    }
    if (isAuthError(envelope.code)) {
      useAuthStore.getState().logout("登录已过期，请重新登录");
    }
    throw new Error(envelope.message || `请求失败 (${response.status})`);
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

export async function stopGeneration(threadId: string): Promise<void> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  try {
    const res = await fetch(`${API_URL}/chat/stop`, {
      method: "POST",
      headers,
      body: JSON.stringify({ thread_id: threadId }),
      credentials: "include",
    });
    checkAuthEnvelope(await res.json().catch(() => null));
  } catch {
    // 认证失败已登出，其余错误忽略（停止为尽力而为）
  }
}

/**
 * 恢复被 HITL 中断的对话：把用户审批决策发给后端，续流返回 SSE 事件。
 *
 * decisions 顺序须与 approval_needed 的 action_requests 对齐。
 * reject 可带 reason（修订稿），后端注入为 reject 消息引导 agent 重新提案。
 */
export async function* resumeChat(
  threadId: string,
  decisions: { type: "approve" | "reject"; reason?: string }[],
  signal?: AbortSignal
): AsyncGenerator<SSEEvent> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  const response = await fetch(`${API_URL}/chat/resume`, {
    method: "POST",
    headers,
    body: JSON.stringify({ thread_id: threadId, decisions }),
    signal,
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
  }

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("text/event-stream")) {
    let envelope: { code?: number; message?: string } = {};
    try {
      envelope = await response.json();
    } catch {
      // 非 JSON 响应，忽略解析
    }
    if (isAuthError(envelope.code)) {
      useAuthStore.getState().logout("登录已过期，请重新登录");
    }
    throw new Error(envelope.message || `请求失败 (${response.status})`);
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
