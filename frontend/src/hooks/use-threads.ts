import { useCallback, useEffect, useState } from "react";
import type { Thread } from "@/types/chat";
import { API_URL, checkAuthEnvelope } from "@/lib/api";

export function useThreads() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadThreads = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/chat/threads`, {
        credentials: "include",
      });
      if (res.ok) {
        const json = await res.json();
        checkAuthEnvelope(json);
        // 后端 ResponseModel: { code, message, data: [...] }
        const list = json.data || [];
        // 映射 thread_id → id 以适配前端 Thread 类型
        setThreads(
          list.map((t: Record<string, unknown>) => ({
            id: t.thread_id as string,
            title: (t.title as string | null) ?? null,
            lastMessage: (t.last_message as string) ?? null,
            createdAt: t.created_at as string,
            updatedAt: t.updated_at as string,
            messageCount: (t.message_count as number) || 0,
            totalTokens: (t.total_tokens as number) || 0,
            agentMode: (t.agent_mode as string) ?? undefined,
          }))
        );
      }
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadThreads();
  }, [loadThreads]);

  const deleteThread = useCallback(async (id: string) => {
    try {
      const res = await fetch(`${API_URL}/chat/threads/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      checkAuthEnvelope(await res.json().catch(() => null));
      if (!res.ok) return;
      setThreads((prev) => prev.filter((t) => t.id !== id));
    } catch {
      // 认证失败已登出，其余错误忽略
    }
  }, []);

  const clearHistory = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/chat/history`, {
        method: "DELETE",
        credentials: "include",
      });
      checkAuthEnvelope(await res.json().catch(() => null));
      if (!res.ok) return;
      setThreads([]);
    } catch {
      // 认证失败已登出，其余错误忽略
    }
  }, []);

  const renameThread = useCallback(async (id: string, title: string) => {
    const trimmed = title.trim();
    if (!trimmed) return false;
    // 乐观更新，失败时回滚
    setThreads((prev) =>
      prev.map((t) => (t.id === id ? { ...t, title: trimmed } : t))
    );
    try {
      const res = await fetch(`${API_URL}/chat/threads/${id}/title`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: trimmed }),
        credentials: "include",
      });
      const json = await res.json().catch(() => null);
      checkAuthEnvelope(json);
      if (!res.ok || !json) {
        // 回滚：重新加载以恢复服务端真实状态
        loadThreads();
        return false;
      }
      return true;
    } catch {
      loadThreads();
      return false;
    }
  }, [loadThreads]);

  return { threads, isLoading, loadThreads, deleteThread, clearHistory, renameThread };
}
