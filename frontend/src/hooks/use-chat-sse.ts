import { useCallback, useEffect, useRef, useState } from "react";
import { nanoid } from "nanoid";
import { resumeChat, streamChat, stopGeneration } from "@/lib/sse-client";
import { useChatStore } from "@/stores/chat-store";
import type { AgentStep, ChatMessage, ToolApproval, ToolCall, TokenUsage } from "@/types/chat";

/** 待审批的 HITL 请求（仅当前流式消息携带，交互态；历史消息的 approvals 为只读） */
export interface PendingApproval {
  messageId: string;
  approvals: ToolApproval[];
  threadId: string;
}

export function useChatSSE(
  threadId: string | null,
  onUsageCommitted?: (usage: TokenUsage) => void
) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [thinking, setThinking] = useState("");
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null);
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
  // pendingApproval 的 ref 镜像：resume() 内读取当前值（setState 异步）
  const pendingApprovalRef = useRef<PendingApproval | null>(null);
  useEffect(() => {
    pendingApprovalRef.current = pendingApproval;
  }, [pendingApproval]);
  useEffect(() => {
    onUsageCommittedRef.current = onUsageCommitted;
  });
  useEffect(() => {
    activeThreadIdRef.current = threadId;
  }, [threadId]);

  // 使用 store 统一管理 currentThreadId，避免状态不同步
  const setThreadId = useChatStore((s) => s.setThreadId);

  /** 从 approval_needed 事件载荷构建 ToolApproval 列表 */
  const buildApprovals = useCallback(
    (data: Record<string, unknown>): ToolApproval[] => {
      const ars = (data.action_requests as Array<Record<string, unknown>>) || [];
      return ars.map((ar) => ({
        id: (ar.id as string) || "",
        tool: (ar.tool as string) || "",
        input: (ar.input as Record<string, unknown>) || {},
        description: (ar.description as string) || undefined,
        allowedDecisions:
          (ar.allowed_decisions as string[]) || ["approve", "reject"],
        state: "approval-requested",
      }));
    },
    []
  );

  /** 累加 usage 到会话总量（sendMessage 与 resume 共用） */
  const accumulateUsage = useCallback((u: TokenUsage) => {
    const next = {
      input_tokens: usageRef.current.input_tokens + (u.input_tokens || 0),
      output_tokens: usageRef.current.output_tokens + (u.output_tokens || 0),
      total_tokens: usageRef.current.total_tokens + (u.total_tokens || 0),
    };
    usageRef.current = next;
    setUsage(next);
    const tid = activeThreadIdRef.current;
    if (tid) usageCacheRef.current.set(tid, next);
  }, []);

  /**
   * 处理流式增量事件（thinking/token/step/tool_start/tool_result），
   * 追加到指定 assistantId 消息。sendMessage 与 resume 共用，保证两路行为一致。
   * fullThinkingRef 为本地累积思考文本 ref，用于计算工具块在思考流中的插入位置。
   */
  const applyStreamDelta = useCallback(
    (
      event: { event: string; data: Record<string, unknown> },
      assistantId: string,
      fullThinkingRef: { current: string }
    ) => {
      switch (event.event) {
        case "thinking": {
          const delta = (event.data.content as string) || "";
          fullThinkingRef.current += delta;
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

        case "step": {
          const s = event.data as {
            type: string;
            id?: string;
            delta?: string;
            tool?: string;
            input?: Record<string, unknown>;
            data?: unknown;
          };
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== assistantId) return m;
              const steps = [...(m.steps || [])];
              if (s.type === "thought") {
                const last = steps[steps.length - 1];
                if (last && last.type === "thought") {
                  steps[steps.length - 1] = {
                    ...last,
                    content: (last.content || "") + (s.delta || ""),
                  };
                } else {
                  steps.push({ type: "thought", content: s.delta || "" });
                }
              } else if (s.type === "tool") {
                steps.push({
                  type: "tool",
                  id: (s.id as string) || nanoid(),
                  tool: s.tool,
                  input: (s.input as Record<string, unknown>) || {},
                  status: "running",
                });
              } else if (s.type === "tool_result") {
                const idx = steps.findIndex(
                  (st) => st.type === "tool" && st.id === s.id
                );
                if (idx !== -1) {
                  steps[idx] = {
                    ...steps[idx],
                    output: s.data,
                    status: "completed",
                  } as AgentStep;
                }
              }
              return { ...m, steps };
            })
          );
          break;
        }

        case "tool_start": {
          const toolCall: ToolCall = {
            id: (event.data.id as string) || nanoid(),
            name: (event.data.tool as string) || "unknown",
            input: (event.data.input as Record<string, unknown>) || {},
            status: "running",
            thinkingOffset: fullThinkingRef.current.length,
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
              let idx = -1;
              if (toolId) {
                idx = calls.findIndex((c) => c.id === toolId);
              }
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
      }
    },
    []
  );

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
      // 用 ref-like 对象传递给共享处理器（applyStreamDelta 期望可变 .current）
      const fullThinkingRef = { current: "" };

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

            case "thinking":
            case "token":
            case "step":
            case "tool_start":
            case "tool_result":
              applyStreamDelta(event, assistantId, fullThinkingRef);
              break;

            case "approval_needed": {
              // HITL 中断：把审批请求挂到当前 assistant 消息，停止流式等待用户决策
              const approvals = buildApprovals(event.data);
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, approvals, isStreaming: false }
                    : m
                )
              );
              setPendingApproval({
                messageId: assistantId,
                approvals,
                threadId: (event.data.thread_id as string) || activeThreadIdRef.current || "",
              });
              break;
            }

            case "usage": {
              accumulateUsage(event.data as unknown as TokenUsage);
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
    [threadId, isStreaming, setThreadId, applyStreamDelta, buildApprovals, accumulateUsage]
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

  /**
   * 恢复被 HITL 中断的对话：把用户审批决策发给后端，续流追加到原 assistant 消息。
   *
   * - approve：工具执行落库，流式续传总结
   * - reject（无 reason）：终结该轮，可对话继续
   * - reject（带 reason=修订稿）：agent 重新提案并可能再次中断（新的 approval_needed）
   *
   * 乐观更新审批状态；resume 期间再次中断则追加新审批并等待下一次决策。
   */
  const resume = useCallback(
    async (decisions: { type: "approve" | "reject"; reason?: string }[]) => {
      const pa = pendingApprovalRef.current;
      if (!pa || isStreaming) return;
      const assistantId = pa.messageId;
      const tid = pa.threadId;
      const dec = decisions[0];
      const approved = dec.type === "approve";

      // 乐观更新：当前审批进入 responded 态
      setMessages((prev) =>
        prev.map((m) => {
          if (m.id !== assistantId || !m.approvals) return m;
          const approvals = m.approvals.map((a, i) =>
            i === m.approvals.length - 1
              ? {
                  ...a,
                  state: "approval-responded" as const,
                  approved,
                  decision: dec.type,
                }
              : a
          );
          return { ...m, approvals, isStreaming: true };
        })
      );
      setPendingApproval(null);
      setIsStreaming(true);
      setThinking("");

      const controller = new AbortController();
      abortRef.current = controller;
      const fullThinkingRef = { current: "" };

      try {
        for await (const event of resumeChat(tid, decisions, controller.signal)) {
          switch (event.event) {
            case "thinking":
            case "token":
            case "step":
            case "tool_start":
            case "tool_result":
              applyStreamDelta(event, assistantId, fullThinkingRef);
              break;

            case "approval_needed": {
              // resume 后再次中断（reject 带修订稿 -> 重新提案）：
              // 旧审批标记为 denied，追加新审批并等待下一次决策
              const newApprovals = buildApprovals(event.data);
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId) return m;
                  // 旧审批终结：已响应按结果转 output-*，未响应的标记 denied
                  const old = (m.approvals || []).map((a) => {
                    if (a.state === "approval-responded") {
                      return {
                        ...a,
                        state: (a.approved ? "output-available" : "output-denied") as
                          | "output-available"
                          | "output-denied",
                      };
                    }
                    if (a.state === "approval-requested") {
                      return {
                        ...a,
                        state: "output-denied" as const,
                        approved: false,
                        decision: "reject" as const,
                      };
                    }
                    return a;
                  });
                  return { ...m, approvals: [...old, ...newApprovals], isStreaming: false };
                })
              );
              setPendingApproval({ messageId: assistantId, approvals: newApprovals, threadId: tid });
              break;
            }

            case "usage":
              accumulateUsage(event.data as unknown as TokenUsage);
              break;

            case "done":
              // 终结审批态：approve -> output-available；reject -> output-denied
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantId || !m.approvals) return m;
                  const approvals = m.approvals.map((a) =>
                    a.state === "approval-responded"
                      ? {
                          ...a,
                          state: (approved ? "output-available" : "output-denied") as
                            | "output-available"
                            | "output-denied",
                        }
                      : a
                  );
                  return { ...m, approvals, isStreaming: false };
                })
              );
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
    [isStreaming, applyStreamDelta, buildApprovals, accumulateUsage]
  );

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

  return { messages, sendMessage, stop, resume, clearMessages, isStreaming, thinking, setMessages, usage, seedUsage, pendingApproval };
}