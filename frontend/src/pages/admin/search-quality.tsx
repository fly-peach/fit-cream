import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import {
  SearchIcon,
  Loader2,
  PlayIcon,
  DatabaseZapIcon,
  RefreshCwIcon,
  AlertCircleIcon,
  CheckCircle2Icon,
  ChevronDownIcon,
  ChevronRightIcon,
  TargetIcon,
  ListChecksIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import {
  adminApi,
  type BackfillStatus,
  type SearchQualityEval,
} from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/** 数值格式化：null -> 占位；0-1 指标按百分比（MRR 保留两位小数） */
function pct(v: number | null | undefined): string {
  if (v == null) return "—";
  return `${(v * 100).toFixed(1)}%`;
}

function dec(v: number | null | undefined): string {
  if (v == null) return "—";
  return v.toFixed(2);
}

function MetricCard({
  icon,
  label,
  value,
  baseline,
  baselineLabel,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  baseline: string;
  baselineLabel: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-emerald-50/50 px-3.5 py-3">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="truncate text-xs text-emerald-600/60">{label}</p>
        <p className="text-xl font-bold tabular-nums text-emerald-950">
          {value}
          <span className="ml-1.5 text-xs font-medium text-emerald-500/70">
            {baselineLabel} {baseline}
          </span>
        </p>
      </div>
    </div>
  );
}

export default function AdminSearchQualityPage() {
  const [k, setK] = useState("20");
  const [evaluating, setEvaluating] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SearchQualityEval | null>(null);

  const [backfill, setBackfill] = useState<BackfillStatus | null>(null);
  const [backfillMsg, setBackfillMsg] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const runEval = useCallback(async () => {
    setEvaluating(true);
    setError("");
    try {
      const data = await adminApi.runSearchQualityEval(Number(k));
      setResult(data);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "评估失败，请重试");
    } finally {
      setEvaluating(false);
    }
  }, [k]);

  // 回填状态：加载一次 + running 时轮询
  const loadStatus = useCallback(async () => {
    try {
      const s = await adminApi.getSearchBackfillStatus();
      setBackfill(s);
    } catch {
      /* 状态加载失败不打断页面 */
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  useEffect(() => {
    if (backfill?.running) {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(() => void loadStatus(), 3000);
    } else if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [backfill?.running, loadStatus]);

  const triggerBackfill = useCallback(
    async (force: boolean) => {
      setBackfillMsg("");
      try {
        const r = await adminApi.triggerSearchBackfill(force);
        setBackfillMsg(r.message);
        await loadStatus();
      } catch (e) {
        setBackfillMsg(e instanceof ApiError ? e.message : "触发失败");
      }
    },
    [loadStatus]
  );

  const [expanded, setExpanded] = useState<string | null>(null);

  const fd = result?.aggregates.filter_derived.by_mode.vector_rerank;
  const fdBase = result?.aggregates.filter_derived.by_mode.vector;
  const hp = result?.aggregates.hand_picked.by_mode.vector_rerank;
  const hpBase = result?.aggregates.hand_picked.by_mode.vector;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 p-4 md:p-6">
      {/* 操作区 */}
      <Card className="border-emerald-100 bg-white/80">
        <CardContent className="flex flex-col gap-3 p-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="flex items-center gap-2 text-lg font-bold text-emerald-950">
              <SearchIcon className="size-5 text-emerald-500" />
              动作库检索质量
            </h1>
            <p className="mt-1 text-xs text-emerald-700/70">
              黄金集 Recall@K 离线评估（schema v2，25 条查询）与 embedding 回填。
              评估实时执行，约需 30-60 秒。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Select value={k} onValueChange={setK}>
              <SelectTrigger className="w-[104px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">K = 10</SelectItem>
                <SelectItem value="20">K = 20</SelectItem>
                <SelectItem value="50">K = 50</SelectItem>
              </SelectContent>
            </Select>
            <Button
              onClick={() => void runEval()}
              disabled={evaluating}
              className="bg-emerald-600 text-white hover:bg-emerald-700"
            >
              {evaluating ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <PlayIcon className="size-4" />
              )}
              {evaluating ? "评估中…" : "运行评估"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertCircleIcon className="size-4 shrink-0" />
          {error}
        </div>
      )}

      {/* 指标卡 */}
      {result && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            icon={<TargetIcon className="size-4" />}
            label="过滤查询 precision@K（混合+精排）"
            value={pct(fd?.average_precision_at_k)}
            baseline={pct(fdBase?.average_precision_at_k)}
            baselineLabel="纯向量"
          />
          <MetricCard
            icon={<CheckCircle2Icon className="size-4" />}
            label="过滤查询 hit_rate@10（混合+精排）"
            value={pct(fd?.average_hit_rate_at_10)}
            baseline={pct(fdBase?.average_hit_rate_at_10)}
            baselineLabel="纯向量"
          />
          <MetricCard
            icon={<SearchIcon className="size-4" />}
            label="语义查询 recall@K（混合+精排）"
            value={pct(hp?.average_recall_at_k)}
            baseline={pct(hpBase?.average_recall_at_k)}
            baselineLabel="纯向量"
          />
          <MetricCard
            icon={<ListChecksIcon className="size-4" />}
            label="语义查询 MRR@K（混合+精排）"
            value={dec(hp?.average_mrr_at_k)}
            baseline={dec(hpBase?.average_mrr_at_k)}
            baselineLabel="纯向量"
          />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* 明细表 */}
        <Card className="border-emerald-100 bg-white/80 lg:col-span-2">
          <CardContent className="p-4">
            <p className="mb-3 text-sm font-semibold text-emerald-950">
              黄金集明细（{result ? `${result.total_queries} 条` : "尚未评估"}）
            </p>
            {!result ? (
              <p className="py-8 text-center text-sm text-emerald-700/50">
                点击「运行评估」后展示每条查询的分模式指标
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[680px] text-left text-sm">
                  <thead>
                    <tr className="border-b border-emerald-100 text-xs text-emerald-700/60">
                      <th className="py-2 pr-2 font-medium">查询</th>
                      <th className="py-2 pr-2 font-medium">类型</th>
                      <th className="py-2 pr-2 font-medium">相关集</th>
                      <th className="py-2 pr-2 font-medium">主指标（混合+精排）</th>
                      <th className="py-2 pr-2 font-medium">词项命中</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.details.map((d) => {
                      const mode = d.per_mode?.vector_rerank ?? {};
                      const isOpen = expanded === d.query;
                      const primary =
                        d.kind === "filter_derived"
                          ? `${pct(mode.precision_at_k)} / ${pct(mode.hit_rate_at_10)}`
                          : `${pct(mode.recall_at_k)} / ${dec(mode.mrr_at_k)}`;
                      const primaryLabel =
                        d.kind === "filter_derived" ? "precision/hit10" : "recall/MRR";
                      return (
                        <Fragment key={d.query}>
                          <tr
                            className="cursor-pointer border-b border-emerald-50 hover:bg-emerald-50/40"
                            onClick={() => setExpanded(isOpen ? null : d.query)}
                          >
                            <td className="py-2 pr-2">
                              <span className="flex items-center gap-1 font-medium text-emerald-950">
                                {isOpen ? (
                                  <ChevronDownIcon className="size-3.5 shrink-0 text-emerald-400" />
                                ) : (
                                  <ChevronRightIcon className="size-3.5 shrink-0 text-emerald-400" />
                                )}
                                {d.query}
                              </span>
                            </td>
                            <td className="py-2 pr-2 text-xs text-emerald-700/70">
                              {d.kind === "filter_derived" ? "过滤派生" : "语义手挑"}
                            </td>
                            <td className="py-2 pr-2 tabular-nums text-emerald-800">
                              {d.relevant_count}
                            </td>
                            <td className="py-2 pr-2 tabular-nums text-emerald-800">
                              {primary}
                              <span className="ml-1 text-[10px] text-emerald-500/70">
                                {primaryLabel}
                              </span>
                            </td>
                            <td className="py-2 pr-2 tabular-nums text-emerald-800">
                              {d.hit_counts?.keyword_terms ?? "—"}
                            </td>
                          </tr>
                          {isOpen && (
                            <tr className="bg-emerald-50/30">
                              <td colSpan={5} className="px-3 py-2.5">
                                <p className="mb-1 text-xs font-medium text-emerald-700/70">
                                  top-10（混合+精排）：
                                  {d.keyword_terms?.length
                                    ? ` 词项：${d.keyword_terms.join(" / ")}`
                                    : ""}
                                </p>
                                <p className="text-xs leading-5 text-emerald-900/80">
                                  {(d.vector_rerank_top10 ?? []).join(" · ") || "无命中"}
                                </p>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <div className="space-y-4">
          {/* 零命中 */}
          <Card className="border-emerald-100 bg-white/80">
            <CardContent className="p-4">
              <p className="mb-2 text-sm font-semibold text-emerald-950">零命中查询</p>
              {!result ? (
                <p className="text-sm text-emerald-700/50">尚未评估</p>
              ) : result.zero_hit_queries.length === 0 ? (
                <p className="flex items-center gap-1.5 text-sm text-emerald-700">
                  <CheckCircle2Icon className="size-4 text-emerald-500" />
                  无零命中（零命中反例不计入）
                </p>
              ) : (
                <ul className="space-y-1 text-sm text-red-700">
                  {result.zero_hit_queries.map((z) => (
                    <li key={z.query} className="flex items-center gap-1.5">
                      <AlertCircleIcon className="size-3.5 shrink-0" />
                      {z.query}
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* 回填 */}
          <Card className="border-emerald-100 bg-white/80">
            <CardContent className="space-y-3 p-4">
              <p className="flex items-center gap-2 text-sm font-semibold text-emerald-950">
                <DatabaseZapIcon className="size-4 text-emerald-500" />
                embedding 回填
              </p>
              <p className="text-xs leading-5 text-emerald-700/70">
                检索文本（build_embedding_text）变更后需全量重算；
                增量回填仅补空值。后台任务执行，可重复触发。
              </p>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                  disabled={backfill?.running}
                  onClick={() => void triggerBackfill(false)}
                >
                  增量回填
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                  disabled={backfill?.running}
                  onClick={() => void triggerBackfill(true)}
                >
                  <RefreshCwIcon className="size-3.5" />
                  全量重算
                </Button>
              </div>
              {(backfillMsg || backfill?.result?.message) && (
                <p
                  className={cn(
                    "text-xs",
                    backfill?.running ? "text-emerald-600" : "text-emerald-700"
                  )}
                >
                  {backfill?.running && (
                    <Loader2 className="mr-1 inline size-3 animate-spin align-[-1px]" />
                  )}
                  {backfill?.running ? "回填任务执行中，每 3 秒刷新状态…" : ""}
                  {backfillMsg && !backfill?.running ? backfillMsg : ""}
                  {backfill?.result?.message && !backfillMsg
                    ? backfill.result.message
                    : ""}
                </p>
              )}
              {backfill && !backfill.running && !backfill.result && (
                <p className="text-xs text-emerald-700/50">暂无历史回填记录</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
