import { useCallback, useRef, useState } from "react";
import { nanoid } from "nanoid";
import { streamChat, stopGeneration } from "@/lib/sse-client";
import { useChatStore } from "@/stores/chat-store";
import type { ChatMessage, ToolCall } from "@/types/chat";

function getToken(): string | null {
  return localStorage.getItem("fitcream_token");
}

export function useChatSSE(threadId: string | null) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinking, setThinking] = useState("");
  const abortRef = useRef<AbortController | null>(null);

  // 使用 store 统一管理 currentThreadId，避免状态不同步
  const setThreadId = useChatStore((s) => s.setThreadId);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return;

      // Add user message
      const userMsg: ChatMessage = {
        id: nanoid(),
        role: "user",
        content,
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
        for await (const event of streamChat(content, threadId, controller.signal, token)) {
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
                id: nanoid(),
                name: (event.data.tool as string) || "unknown",
                input: {},
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
              const toolName = event.data.tool as string;
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  const calls = [...(m.toolCalls || [])];
                  for (let i = calls.length - 1; i >= 0; i--) {
                    if (calls[i].name === toolName && calls[i].status === "running") {
                      calls[i] = { ...calls[i], output: event.data.data as string, status: "completed" };
                      break;
                    }
                  }
                  return { ...m, toolCalls: calls };
                })
              );
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
  }, []);

  return { messages, sendMessage, stop, clearMessages, isStreaming, thinking, setMessages };
}