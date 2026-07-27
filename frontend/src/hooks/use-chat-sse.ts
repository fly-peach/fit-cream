import { useCallback, useRef, useState } from "react";
import { nanoid } from "nanoid";
import { streamChat, stopGeneration } from "@/lib/sse-client";
import { useChatStore } from "@/stores/chat-store";
import type { ChatMessage, ToolCall, TokenUsage } from "@/types/chat";

function getToken(): string | null {
  return localStorage.getItem("fitcream_token");
}

export function useChatSSE(threadId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinking, setThinking] = useState("");
  // 当前会话累计 Token 使用量（用于 Context 组件展示）
  const [usage, setUsage] = useState<TokenUsage>({
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
  });
  const abortRef = useRef<AbortController | null>(null);

  // 使用 store 统一管理 currentThreadId，避免状态不同步
  const setThreadId = useChatStore((s) => s.setThreadId);

  const sendMessage = useCallback(
    async (content: string, images?: string[]) => {
      const hasText = content.trim().length > 0;
      const hasImages = !!images && images.length > 0;
      if ((!hasText && !hasImages) || isStreaming) return;

      // Add user message
      const userMsg: ChatMessage = {
        id: nanoid(),
        role: "user",
        content: hasText ? content : "[图片消息]",
        images: hasImages ? images : undefined,
        createdAt: Date.now(),
      };

      // Create assistant placeholder
      const assistantId = nanoid();
      const assistantMsg: ChatMessage = {
        id: assistantId,
        role: "assistant",
        content: "",
        thinking: "",
        toolCalls: [],
        createdAt: Date.now(),
        isStreaming: true,
      };

      setMessages((prev) => [...prev, userMsg, assistantMsg]);
      setIsStreaming(true);
      setThinking("");

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const token = getToken() || undefined;
        for await (const event of streamChat(content, threadId, controller.signal, token, images)) {
          switch (event.event) {
            case "start":
              // 后端返回 thread_id，同步到全局 store
              if (event.data.thread_id) {
                setThreadId(event.data.thread_id as string);
              }
              break;

            case "thinking":
              setThinking((prev) => prev + (event.data.content as string));
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, thinking: (m.thinking || "") + (event.data.content as string) }
                    : m
                )
              );
              break;

            case "token":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: m.content + (event.data.content as string) }
                    : m
                )
              );
              break;

            case "tool_start": {
              const toolCall: ToolCall = {
                // 使用后端返回的 run_id，便于 tool_result 精确匹配（多轮调用时同名工具不会错乱）
                id: (event.data.id as string) || nanoid(),
                name: (event.data.tool as string) || "unknown",
                input: (event.data.input as Record<string, unknown>) || {},
                status: "running",
              };
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, toolCalls: [...(m.toolCalls || []), toolCall] }
                    : m
                )
              );
              break;
            }

            case "tool_result": {
              const toolId = event.data.id as string | undefined;
              const toolName = event.data.tool as string;
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  const calls = [...(m.toolCalls || [])];
                  // 优先按后端返回的 id 精确匹配
                  let idx = -1;
                  if (toolId) {
                    idx = calls.findIndex((c) => c.id === toolId);
                  }
                  // 兜底：按名称匹配最后一个 running 状态的调用
                  if (idx === -1) {
                    for (let i = calls.length - 1; i >= 0; i--) {
                      if (calls[i].name === toolName && calls[i].status === "running") {
                        idx = i;
                        break;
                      }
                    }
                  }
                  if (idx !== -1) {
                    calls[idx] = { ...calls[idx], output: event.data.data as string, status: "completed" };
                  }
                  return { ...m, toolCalls: calls };
                })
              );
              break;
            }

            case "usage": {
              // 后端返回本轮 token 使用量，累加到会话总量
              const u = event.data as unknown as TokenUsage;
              setUsage((prev) => ({
                input_tokens: prev.input_tokens + (u.input_tokens || 0),
                output_tokens: prev.output_tokens + (u.output_tokens || 0),
                total_tokens: prev.total_tokens + (u.total_tokens || 0),
              }));
              break;
            }

            case "done":
            case "stopped":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, isStreaming: false } : m
                )
              );
              break;

            case "error":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: `Error: ${event.data.message}`, isStreaming: false }
                    : m
                )
              );
              break;
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: `Error: ${(err as Error).message}`, isStreaming: false }
                : m
            )
          );
        }
      } finally {
        setIsStreaming(false);
        setThinking("");
        abortRef.current = null;
      }
    },
    [threadId, isStreaming, setThreadId]
  );

  const stop = useCallback(async () => {
    abortRef.current?.abort();
    // 从 store 获取最新的 threadId
    const tid = useChatStore.getState().currentThreadId || threadId;
    if (tid) {
      const token = getToken() || undefined;
      await stopGeneration(tid, token);
    }
    setIsStreaming(false);
  }, [threadId]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setUsage({ input_tokens: 0, output_tokens: 0, total_tokens: 0 });
  }, []);

  return { messages, sendMessage, stop, clearMessages, isStreaming, thinking, setMessages, usage, setUsage };
}