import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Plus, Search, ExternalLink, Heart } from "lucide-react";
import { api, exerciseFavApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { muscleGroupLabels, equipmentLabels } from "@/lib/exercise-labels";
import type { Exercise } from "@/types/exercise";

export function ExerciseSearchInline({
  onPick,
  onResultsChange,
}: {
  onPick: (ex: Exercise) => Promise<void> | void;
  onResultsChange?: (hasResults: boolean) => void;
}) {
  const [q, setQ] = useState("");
  const [committed, setCommitted] = useState("");
  const [results, setResults] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(false);
  const [adding, setAdding] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [focused, setFocused] = useState(false);
  const [favIds, setFavIds] = useState<Set<string>>(new Set());
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    exerciseFavApi.listIds().then((ids) => setFavIds(new Set(ids))).catch(() => {});
  }, []);

  const doSearch = useCallback((term: string) => {
    setLoading(true);
    setError("");
    setCommitted(term);
  }, []);

  useEffect(() => {
    let cancelled = false;
    const params = committed.trim()
      ? `keyword=${encodeURIComponent(committed.trim())}&limit=12`
      : "limit=12";
    api
      .get<Exercise[]>(`/exercises?${params}`)
      .then((list) => {
        if (!cancelled) {
          const sorted = [...(list ?? [])].sort((a, b) => {
            const af = favIds.has(a.id) ? 0 : 1;
            const bf = favIds.has(b.id) ? 0 : 1;
            return af - bf;
          });
          setResults(sorted);
          setLoading(false);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError((e as Error).message);
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [committed, favIds]);

  useEffect(() => {
    onResultsChange?.(results.length > 0);
  }, [results, onResultsChange]);

  useEffect(() => {
    const term = q.trim();
    if (!term) {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      setCommitted("");
      return;
    }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      doSearch(term);
    }, 150);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [q, doSearch]);

  const submit = () => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    doSearch(q.trim());
  };

  const pick = async (ex: Exercise) => {
    setAdding(ex.id);
    try {
      await onPick(ex);
      setQ("");
      setCommitted("");
      setResults([]);
    } finally {
      setAdding(null);
    }
  };

  const showPanel = focused || results.length > 0 || loading;

  return (
    <div className="space-y-2 rounded-lg border border-emerald-100 bg-emerald-50/40 p-2">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-emerald-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onFocus={() => {
              setFocused(true);
              if (!committed) doSearch("");
            }}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="搜索动作名称（如 卧推 / 深蹲），或点击浏览"
            className="h-9 rounded-lg border-emerald-200 bg-white/70 pl-9"
          />
        </div>
        <Button
          size="sm"
          variant="outline"
          className="border-emerald-200 text-emerald-700"
          onClick={submit}
        >
          搜索
        </Button>
      </div>
      {showPanel && (
        <>
          {loading && (
            <div className="flex justify-center py-2">
              <Loader2 className="size-4 animate-spin text-emerald-500" />
            </div>
          )}
          {error && <p className="px-1 text-xs text-red-500">{error}</p>}
          {!loading && committed && results.length === 0 && (
            <p className="py-2 text-center text-xs text-emerald-600/50">
              未找到「{committed}」相关动作，试试更短/更通用的关键词
            </p>
          )}
          {results.length > 0 && (
            <div className="max-h-56 space-y-1 overflow-y-auto">
              {!committed.trim() && (
                <p className="px-2 pb-1 text-[11px] text-emerald-500/70">热门动作（输入关键词可精确搜索）</p>
              )}
              {results.map((ex) => (
                <div
                  key={ex.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => pick(ex)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      pick(ex);
                    }
                  }}
                  aria-disabled={adding === ex.id}
                  className={cn(
                    "flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-emerald-100/70",
                    adding === ex.id && "cursor-wait opacity-60",
                  )}
                >
                  {adding === ex.id ? (
                    <Loader2 className="size-3.5 shrink-0 animate-spin text-emerald-500" />
                  ) : (
                    <Plus className="size-3.5 shrink-0 text-emerald-400" />
                  )}
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-emerald-950">
                    {ex.name}
                  </span>
                  {favIds.has(ex.id) && (
                    <Heart className="size-3 shrink-0 fill-rose-400 text-rose-400" />
                  )}
                  {ex.muscle_group && (
                    <Badge
                      variant="outline"
                      className="h-5 shrink-0 border-emerald-200 px-1.5 text-[10px] text-emerald-600"
                    >
                      {muscleGroupLabels[ex.muscle_group] ?? ex.muscle_group}
                    </Badge>
                  )}
                  {ex.equipment && (
                    <Badge
                      variant="outline"
                      className="h-5 shrink-0 border-sky-200 bg-sky-50 px-1.5 text-[10px] text-sky-600"
                    >
                      {equipmentLabels[ex.equipment] ?? ex.equipment}
                    </Badge>
                  )}
                  <a
                    href={`/exercises/${ex.id}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="在新页面查看动作详情"
                    onClick={(e) => e.stopPropagation()}
                    className="flex size-6 shrink-0 items-center justify-center rounded-md text-emerald-400 transition-colors hover:bg-emerald-200 hover:text-emerald-600"
                  >
                    <ExternalLink className="size-3.5" />
                  </a>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
