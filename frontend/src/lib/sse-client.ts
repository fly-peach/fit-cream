import type { SSEEvent } from "@/types/chat";
import { API_URL, checkAuthEnvelope, isAuthError } from "@/lib/api";
import { getDsKey } from "@/lib/ds-key";
import { useAuthStore } from "@/stores/auth-store";

/** 解析非 SSE 的 JSON 业务错误信封并抛出（携带业务 code，供调用方特判如余额不足） */
function throwEnvelopeError(
  envelope: { code?: number; message?: string },
  status: number
): never {
  if (isAuthError(envelope.code)) {
    useAuthStore.getState().logout("登录已过期，请重新登录");
  }
  const err = new Error(envelope.message || `请求失败 (${status})`) as Error & {
    code?: number;
  };
  if (typeof envelope.code === "number") err.code = envelope.code;
  throw err;
}

export async function* streamChat(
  message: string,
  threadId: string | null,
  signal?: AbortSignal,
  images?: string[],
  planDesign?: boolean,
  kbEnabled?: boolean
): AsyncGenerator<SSEEvent> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  const body: Record<string, unknown> = { message, thread_id: threadId };
  if (images && images.length > 0) body.images = images;
  if (planDesign) body.plan_design = true;
  // 仅在开启时发送（关闭省略字段等价 falsy，旧客户端行为不变）
  if (kbEnabled) body.kb_enabled = true;
  // 用户自备 DeepSeek Key：仅随请求体发送（后端不落库、不记日志）
  const dsKey = getDsKey();
  if (dsKey) body.deepseek_api_key = dsKey;

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
    throwEnvelopeError(envelope, response.status);
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
  signal?: AbortSignal,
  kbEnabled?: boolean
): AsyncGenerator<SSEEvent> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };

  const body: Record<string, unknown> = { thread_id: threadId, decisions };
  if (kbEnabled) body.kb_enabled = true;
  // 用户自备 DeepSeek Key：resume 后仍有模型调用，保持一致
  const dsKey = getDsKey();
  if (dsKey) body.deepseek_api_key = dsKey;

  const response = await fetch(`${API_URL}/chat/resume`, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
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
    throwEnvelopeError(envelope, response.status);
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
