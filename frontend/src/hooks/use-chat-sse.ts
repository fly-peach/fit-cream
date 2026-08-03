import { useCallback, useRef, useState } from "react";
import { nanoid } from "nanoid";
import { streamChat, stopGeneration } from "@/lib/sse-client";
import { useChatStore } from "@/stores/chat-store";
import type { ChatMessage, ToolCall, TokenUsage } from "@/types/chat";

export function useChatSSE(
  threadId: string | null,
  onUsageCommitted?: (usage: TokenUsage) => void
) {
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
  // 当前会话累计值同步 ref：setState 异步，done 时需读最终值
  const usageRef = useRef<TokenUsage>({
    input_tokens: 0,
    output_tokens: 0,
    total_tokens: 0,
  });
  // 本页面会话内各线程实时累计值缓存：切换会话不丢已累计增量，避免被历史快照覆盖
  const usageCacheRef = useRef<Map<string, TokenUsage>>(new Map());
  // 当前流式/活动线程 id（新会话由 start 事件创建）
  const activeThreadIdRef = useRef<string | null>(threadId);
  const onUsageCommittedRef = useRef(onUsageCommitted);
  useEffect(() => {
    onUsageCommittedRef.current = onUsageCommitted;
  });
  useEffect(() => {
    activeThreadIdRef.current = threadId;
  }, [threadId]);

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

      // 本地累积思考文本，用于计算工具调用在 thinking 流中的插入位置
      let full_thinking = "";

      try {
        for await (const event of streamChat(content, threadId, controller.signal, images)) {
          switch (event.event) {
            case "start":
              // 后端返回 thread_id，同步到全局 store
              if (event.data.thread_id) {
                const tid = event.data.thread_id as string;
                activeThreadIdRef.current = tid;
                setThreadId(tid);
              }
              break;

            case "thinking": {
              const delta = (event.data.content as string) || "";
              full_thinking += delta;
              setThinking((prev) => prev + delta);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, thinking: (m.thinking || "") + delta }
                    : m
                )
              );
              break;
            }

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
                // 记录工具调用在 thinking 流中的插入位置，便于前端链式渲染
                thinkingOffset: full_thinking.length,
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
              const next = {
                input_tokens: usageRef.current.input_tokens + (u.input_tokens || 0),
                output_tokens: usageRef.current.output_tokens + (u.output_tokens || 0),
                total_tokens: usageRef.current.total_tokens + (u.total_tokens || 0),
              };
              usageRef.current = next;
              setUsage(next);
              const tid = activeThreadIdRef.current;
              if (tid) usageCacheRef.current.set(tid, next);
              break;
            }

            case "done":
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, isStreaming: false } : m
                )
              );
              // 后端已落库 ThreadUsage，通知页面刷新 threads 快照，供切会话 seed 用
              onUsageCommittedRef.current?.({ ...usageRef.current });
              break;
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
      await stopGeneration(tid);
    }
    setIsStreaming(false);
  }, [threadId]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    const zero: TokenUsage = { input_tokens: 0, output_tokens: 0, total_tokens: 0 };
    usageRef.current = zero;
    setUsage(zero);
  }, []);

  // 会话切换时用历史累计值（threads.totalTokens）seed usage；
  // 若本页面已对该会话实时累计过（usageCache），优先用实时值，避免历史快照覆盖。
  const seedUsage = useCallback((threadId: string | null, seed: TokenUsage) => {
    activeThreadIdRef.current = threadId;
    const cached = threadId ? usageCacheRef.current.get(threadId) : undefined;
    const base = cached && cached.total_tokens > 0 ? cached : seed;
    usageRef.current = { ...base };
    setUsage({ ...base });
  }, []);

  return { messages, sendMessage, stop, clearMessages, isStreaming, thinking, setMessages, usage, seedUsage };
}