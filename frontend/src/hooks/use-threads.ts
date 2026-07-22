import { useCallback, useEffect, useState } from "react";
import type { Thread } from "@/types/chat";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

/** 从 localStorage 获取 token（后续接入 auth store） */
function getToken(): string | null {
  return localStorage.getItem("fitcream_token");
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function useThreads() {
  const [threads, setThreads] = useState<Thread[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const loadThreads = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/chat/threads`, {
        headers: authHeaders(),
      });
      if (res.ok) {
        const json = await res.json();
        // 后端 ResponseModel: { code, message, data: [...] }
        const list = json.data || [];
        // 映射 thread_id → id 以适配前端 Thread 类型
        setThreads(
          list.map((t: Record<string, unknown>) => ({
            id: t.thread_id as string,
            title: (t.last_message as string) || "新对话",
            createdAt: t.created_at as string,
            updatedAt: t.updated_at as string,
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
    await fetch(`${API_URL}/chat/threads/${id}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    setThreads((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const clearHistory = useCallback(async () => {
    await fetch(`${API_URL}/chat/history`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    setThreads([]);
  }, []);

  return { threads, isLoading, loadThreads, deleteThread, clearHistory };
}
