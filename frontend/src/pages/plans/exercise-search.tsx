import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2, Plus, Search, ExternalLink } from "lucide-react";
import { api } from "@/lib/api";
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

  useEffect(() => {
    const term = committed.trim();
    if (!term) {
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .get<Exercise[]>(`/exercises?keyword=${encodeURIComponent(term)}&limit=12`)
      .then((list) => {
        if (!cancelled) setResults(list ?? []);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [committed]);

  useEffect(() => {
    onResultsChange?.(results.length > 0);
  }, [results, onResultsChange]);

  const submit = () => setCommitted(q.trim());

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

  return (
    <div className="space-y-2 rounded-lg border border-emerald-100 bg-emerald-50/40 p-2">
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-emerald-400" />
          <Input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="搜索动作名称/说明（如 卧推 / 深蹲）"
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
      {loading && (
        <div className="flex justify-center py-2">
          <Loader2 className="size-4 animate-spin text-emerald-500" />
        </div>
      )}
      {error && <p className="px-1 text-xs text-red-500">{error}</p>}
      {!loading && committed && results.length === 0 && (
        <p className="py-2 text-center text-xs text-emerald-600/50">无匹配动作</p>
      )}
      {results.length > 0 && (
        <div className="max-h-56 space-y-1 overflow-y-auto">
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
    </div>
  );
}
