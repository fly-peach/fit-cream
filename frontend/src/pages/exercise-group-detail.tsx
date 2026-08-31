/**
 * 动作组详情页 /exercises/exercise-group/:key
 *
 * 完整身材内容：大图 + 长文描述 + 核心/体成分指标 + 达成兜底指标 +
 * 推荐动作组（动作可跳详情）+ 阶段叙事。数据复用 GET /goal-knowledge/groups
 * 按 key 过滤当前性别行（toned_curves 等不适配性别时为空态）。
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Loader2,
  Flame,
  Salad,
  Target,
  ImageIcon,
  Sprout,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { api } from "@/lib/api";
import { resolveStaticUrl } from "@/lib/api-url";
import { openDetail } from "@/lib/nav";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/lib/language-context";
import {
  formatGoalMetric,
  goalGroupLabel,
  goalMetricLabel,
} from "@/lib/goal-labels";
import type { GoalExerciseGroupCard, GoalGroupsResponse } from "@/types/goal";

function formatMetricRange(
  m: { metric: string; min?: number | null; max?: number | null },
  isZh: boolean,
): string {
  return formatGoalMetric({ ...m, core: true }, isZh).replace(
    `${goalMetricLabel(m.metric, isZh)} `,
    "",
  );
}

export default function ExerciseGroupDetailPage() {
  const { key } = useParams<{ key: string }>();
  const navigate = useNavigate();
  const { isZh } = useLanguage();
  const [arch, setArch] = useState<GoalExerciseGroupCard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!key) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .get<GoalGroupsResponse>("/goal-knowledge/groups")
      .then((res) => {
        if (!cancelled) {
          setArch((res?.groups ?? []).find((g) => g.key === key) ?? null);
        }
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
  }, [key]);

  const coreMetrics = (arch?.target_metrics ?? []).filter((m) => m.core !== false);
  const displayMetrics = (arch?.target_metrics ?? []).filter((m) => m.core === false);

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-4xl space-y-5 p-3 sm:p-6">
          <Link
            to="/exercises/exercise-group"
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
              "text-emerald-700",
            )}
          >
            <ArrowLeft className="size-4" />
            {isZh ? "返回动作组" : "Back to Groups"}
          </Link>

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          ) : !arch ? (
            <div className="flex flex-col items-center gap-2 py-16 text-center text-emerald-600/50">
              <ImageIcon className="size-8 text-emerald-300" />
              <p className="text-sm">
                {isZh ? "该身材不适用于当前账号性别或不存在" : "Goal not available for your profile"}
              </p>
            </div>
          ) : (
            <>
              <div className="grid gap-5 md:grid-cols-[280px_1fr]">
                {/* 身材图 */}
                <Card className="overflow-hidden border-emerald-100 bg-white/80">
                  <CardContent className="p-3">
                    <div className="relative aspect-[3/4] w-full overflow-hidden rounded-lg bg-emerald-50">
                      {arch.image ? (
                        <img
                          src={resolveStaticUrl(arch.image)}
                          alt={arch.name}
                          className="absolute inset-0 size-full object-cover"
                        />
                      ) : (
                        <div className="flex size-full items-center justify-center text-emerald-200">
                          <ImageIcon className="size-10" />
                        </div>
                      )}
                    </div>
                  </CardContent>
                </Card>

                {/* 概要 */}
                <div className="space-y-4">
                  <div>
                    <h1 className="text-2xl font-bold text-emerald-950">{arch.name}</h1>
                    {arch.tagline && (
                      <p className="mt-1 text-sm text-emerald-600/80">{arch.tagline}</p>
                    )}
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    {arch.stage_hint && (
                      <Badge variant="outline" className="border-emerald-200 text-emerald-600">
                        {isZh ? "预计" : "Est."} {arch.stage_hint}
                      </Badge>
                    )}
                    {arch.training_bias && (
                      <Badge variant="outline" className="border-orange-200 bg-orange-50 text-orange-600">
                        <Flame className="mr-1 size-3" />
                        {arch.training_bias}
                      </Badge>
                    )}
                    {arch.diet_bias && (
                      <Badge variant="outline" className="border-lime-200 bg-lime-50 text-lime-700">
                        <Salad className="mr-1 size-3" />
                        {arch.diet_bias}
                      </Badge>
                    )}
                  </div>

                  {coreMetrics.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {coreMetrics.map((m) => (
                        <Badge
                          key={m.metric}
                          className="border-0 bg-emerald-100 text-emerald-700"
                        >
                          {formatGoalMetric(m, isZh)}
                        </Badge>
                      ))}
                    </div>
                  )}

                  {displayMetrics.length > 0 && (
                    <Card className="border-sky-100 bg-sky-50/40">
                      <CardContent className="p-3">
                        <p className="mb-2 text-xs font-semibold text-sky-700">
                          {isZh ? "体成分参考（体脂秤维度）" : "Body composition reference"}
                        </p>
                        <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                          {displayMetrics.map((m) => (
                            <div
                              key={m.metric}
                              className="flex items-center justify-between text-xs text-sky-800/80"
                            >
                              <span>{goalMetricLabel(m.metric, isZh)}</span>
                              <span className="font-semibold">
                                {formatMetricRange(m, isZh)}
                              </span>
                            </div>
                          ))}
                        </div>
                      </CardContent>
                    </Card>
                  )}
                </div>
              </div>

              {/* 长文描述 */}
              {arch.description && (
                <Card className="border-emerald-100 bg-white/80">
                  <CardContent className="p-4">
                    <h2 className="mb-2 text-sm font-semibold text-emerald-800">
                      {isZh ? "身材解读" : "About this goal"}
                    </h2>
                    <p className="whitespace-pre-line text-sm leading-relaxed text-emerald-800">
                      {arch.description}
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* 达成兜底指标 */}
              {(arch.target_exercise_goal ?? []).length > 0 && (
                <Card className="border-emerald-100 bg-white/80">
                  <CardContent className="p-4">
                    <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-emerald-800">
                      <Target className="size-4 text-emerald-500" />
                      {isZh ? "达成效果兜底指标" : "Achievement baseline"}
                    </h2>
                    <ul className="space-y-1.5">
                      {arch.target_exercise_goal.map((g) => (
                        <li
                          key={g.metric + g.display}
                          className="text-sm text-emerald-800/90"
                        >
                          · {g.display}
                        </li>
                      ))}
                    </ul>
                    <p className="mt-2 text-xs text-emerald-500/70">
                      {isZh
                        ? "以上为人群参考的兜底指标，用于判断方向，不构成达成承诺。"
                        : "Population reference values, not a promise of achievement."}
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* 推荐动作组 */}
              {(arch.exercise_groups ?? []).length > 0 && (
                <Card className="border-emerald-100 bg-white/80">
                  <CardContent className="space-y-3 p-4">
                    <h2 className="text-sm font-semibold text-emerald-800">
                      {isZh ? "推荐动作组" : "Recommended exercise groups"}
                    </h2>
                    {arch.exercise_groups.map((grp) => {
                      const isStretch = grp.group === "拉伸";
                      return (
                        <div key={grp.group ?? "misc"} className="flex flex-wrap items-center gap-2">
                          <span
                            className={cn(
                              "shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold",
                              isStretch
                                ? "bg-violet-100 text-violet-600"
                                : "bg-emerald-100 text-emerald-600",
                            )}
                          >
                            {goalGroupLabel(grp.group, isZh)}
                          </span>
                          <div className="flex min-w-0 flex-wrap gap-1.5">
                            {grp.exercises.map((ex) => (
                              <button
                                key={ex.id}
                                type="button"
                                onClick={() => openDetail(navigate, `/exercises/${ex.id}`)}
                                className={cn(
                                  "rounded-md border px-2 py-0.5 text-xs transition-colors",
                                  isStretch
                                    ? "border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100"
                                    : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100",
                                )}
                              >
                                {isZh ? ex.name : (ex.name_en || ex.name)}
                              </button>
                            ))}
                          </div>
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>
              )}

              {/* 阶段叙事 */}
              {arch.stage_narrative_hint && (
                <Card className="border-emerald-100 bg-white/80">
                  <CardContent className="p-4">
                    <h2 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-emerald-800">
                      <Sprout className="size-4 text-emerald-500" />
                      {isZh ? "阶段路线" : "Stage roadmap"}
                    </h2>
                    <p className="whitespace-pre-line text-sm leading-relaxed text-emerald-800">
                      {arch.stage_narrative_hint}
                    </p>
                  </CardContent>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
