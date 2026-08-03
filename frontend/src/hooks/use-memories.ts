import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SemanticMemoryItem } from "@/types/memory";

export function useMemories() {
  const [data, setData] = useState<SemanticMemoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const list = await api.get<SemanticMemoryItem[]>("/memory/semantic");
      setData(list ?? []);
    } catch (err) {
      // 认证失败已由 api 层自动登出，其余错误展示占位
      setError(err instanceof Error ? err.message : "加载记忆失败");
      setData([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refetch();
  }, [refetch]);

  return { data, loading, error, refetch };
}
