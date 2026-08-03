import { useMemo } from "react";
import { Loader2, RefreshCwIcon, BrainIcon } from "lucide-react";
import { useMemories } from "@/hooks/use-memories";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { SemanticMemoryItem } from "@/types/memory";

const CATEGORY_LABEL: Record<SemanticMemoryItem["category"], string> = {
  preference: "偏好",
  fact: "事实",
  rule: "规则",
  status: "状态",
};

const CATEGORY_ORDER: SemanticMemoryItem["category"][] = [
  "preference",
  "fact",
  "rule",
  "status",
];

const CATEGORY_BADGE_CLASS: Record<SemanticMemoryItem["category"], string> = {
  preference: "bg-emerald-100 text-emerald-700",
  fact: "bg-sky-100 text-sky-700",
  rule: "bg-amber-100 text-amber-700",
  status: "bg-violet-100 text-violet-700",
};

const rtf = new Intl.RelativeTimeFormat("zh-CN", { numeric: "auto" });

function formatRelative(dateStr: string): string {
  const diffMs = new Date(dateStr).getTime() - Date.now();
  const diffDay = Math.round(diffMs / (1000 * 60 * 60 * 24));
  if (Math.abs(diffDay) >= 1) return rtf.format(diffDay, "day");
  const diffHour = Math.round(diffMs / (1000 * 60 * 60));
  if (Math.abs(diffHour) >= 1) return rtf.format(diffHour, "hour");
  const diffMin = Math.round(diffMs / (1000 * 60));
  return rtf.format(diffMin, "minute");
}

function MemoryCard({ item }: { item: SemanticMemoryItem }) {
  return (
    <div className="rounded-xl border border-emerald-100 bg-white p-3.5 shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-start justify-between gap-2">
        <p className="text-sm font-medium text-emerald-950">
          {item.subject}{" "}
          <span className="text-emerald-500">{item.predicate}</span>{" "}
          {item.object}
        </p>
        <Badge
          className={CATEGORY_BADGE_CLASS[item.category]}
          variant="secondary"
        >
          {CATEGORY_LABEL[item.category]}
        </Badge>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-emerald-600/60">
        <span>置信度 {Math.round(item.confidence * 100)}%</span>
        <span>v{item.version}</span>
        <span>{formatRelative(item.updated_at)}</span>
      </div>
    </div>
  );
}

export function MemoryPanel() {
  const { data, loading, error, refetch } = useMemories();

  const grouped = useMemo(() => {
    const map = new Map<SemanticMemoryItem["category"], SemanticMemoryItem[]>();
    for (const item of data) {
      const arr = map.get(item.category) ?? [];
      arr.push(item);
      map.set(item.category, arr);
    }
    return map;
  }, [data]);

  if (loading) {
    return (
      <div className="flex flex-1 items-center justify-center text-emerald-500">
        <Loader2 className="size-6 animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 py-16">
        <p className="text-sm text-red-600">{error}</p>
        <Button
          variant="outline"
          size="sm"
          onClick={refetch}
          className="gap-1.5 rounded-lg border-emerald-200 text-emerald-700 hover:bg-emerald-50"
        >
          <RefreshCwIcon className="size-3.5" />
          重试
        </Button>
      </div>
    );
  }

  if (data.length === 0) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 py-16">
        <div className="flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-100 to-teal-100">
          <BrainIcon className="size-8 text-emerald-500" />
        </div>
        <p className="text-sm text-emerald-700/60">
          AI 教练还没有记住你的信息，多和它聊聊吧
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <div className="mx-auto max-w-3xl space-y-5">
        {CATEGORY_ORDER.filter((c) => grouped.has(c)).map((c) => {
          const items = grouped.get(c)!;
          return (
            <section key={c}>
              <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold text-emerald-900">
                {CATEGORY_LABEL[c]}
                <span className="text-xs font-normal text-emerald-500/70">
                  （{items.length}）
                </span>
              </h2>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {items.map((item) => (
                  <MemoryCard key={item.id} item={item} />
                ))}
              </div>
            </section>
          );
        })}
      </div>
    </div>
  );
}
