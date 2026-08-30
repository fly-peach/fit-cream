/**
 * 动作组页 /exercises/exercise-group
 *
 * 身材原型卡片网格（一行 3 个）：原型图 + 达成指标徽章 + 兜底目标 +
 * 推荐动作组（动作名跳 /exercises/:id，末组「拉伸」高亮）。
 * 数据来自 GET /goal-knowledge/groups（按当前用户性别取行）。
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, Dumbbell, ImageIcon, Target, Flame, Salad } from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { ExerciseTabs } from "@/components/exercise-tabs";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";
import { resolveStaticUrl } from "@/lib/api-url";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/lib/language-context";
import { formatGoalMetric, goalGroupLabel } from "@/lib/goal-labels";
import type { GoalExerciseGroupCard, GoalGroupsResponse } from "@/types/goal";

function GroupCard({ arch }: { arch: GoalExerciseGroupCard }) {
  const { isZh } = useLanguage();
  const coreMetrics = (arch.target_metrics ?? []).filter((m) => m.core !== false);
  const displayMetrics = (arch.target_metrics ?? []).filter((m) => m.core === false);

  return (
    <Card className="group flex h-full flex-col overflow-hidden border-emerald-100 bg-white/80 transition-all hover:border-emerald-300 hover:shadow-md">
      <CardContent className="flex flex-1 flex-col gap-2 p-2">
        <div className="relative aspect-[3/4] w-full overflow-hidden rounded-lg bg-emerald-50">
          {arch.image ? (
            <img
              src={resolveStaticUrl(arch.image)}
              alt={arch.name}
              loading="lazy"
              className="absolute inset-0 size-full object-cover"
            />
          ) : (
            <div className="flex size-full items-center justify-center text-emerald-200">
              <ImageIcon className="size-8" />
            </div>
          )}
          {arch.stage_hint && (
            <Badge className="absolute left-1.5 top-1.5 border-0 bg-black/45 text-[10px] text-white backdrop-blur-sm">
              {arch.stage_hint}
            </Badge>
          )}
        </div>

        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-emerald-950">{arch.name}</h3>
          {arch.tagline && (
            <p className="line-clamp-1 text-xs text-emerald-600/70">{arch.tagline}</p>
          )}
        </div>

        <div className="flex flex-wrap gap-1">
          {coreMetrics.slice(0, 4).map((m) => (
            <Badge
              key={m.metric}
              variant="outline"
              className="border-emerald-200 bg-emerald-50/60 text-[10px] text-emerald-700"
            >
              {formatGoalMetric(m, isZh)}
            </Badge>
          ))}
          {displayMetrics.length > 0 && (
            <Badge
              variant="outline"
              className="border-sky-200 bg-sky-50/60 text-[10px] text-sky-600"
              title={displayMetrics.map((m) => formatGoalMetric(m, isZh)).join(" · ")}
            >
              +{displayMetrics.length} {isZh ? "体成分" : "body comp."}
            </Badge>
          )}
        </div>

        {(arch.target_exercise_goal ?? []).length > 0 && (
          <ul className="space-y-0.5">
            {arch.target_exercise_goal.slice(0, 3).map((g) => (
              <li
                key={g.metric + g.display}
                className="flex items-start gap-1 text-[11px] leading-snug text-emerald-800/80"
              >
                <Target className="mt-0.5 size-3 shrink-0 text-emerald-400" />
                <span className="line-clamp-1">{g.display}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-auto space-y-1 border-t border-emerald-50 pt-1.5">
          {(arch.exercise_groups ?? []).map((grp) => {
            const isStretch = grp.group === "拉伸";
            return (
              <div key={grp.group ?? "misc"} className="flex items-start gap-1.5">
                <span
                  className={cn(
                    "mt-0.5 shrink-0 rounded px-1 py-px text-[10px] font-semibold",
                    isStretch
                      ? "bg-violet-100 text-violet-600"
                      : "bg-emerald-100 text-emerald-600",
                  )}
                >
                  {goalGroupLabel(grp.group, isZh)}
                </span>
                <div className="flex min-w-0 flex-wrap gap-x-1.5 text-[11px] leading-snug">
                  {grp.exercises.map((ex) => (
                    <Link
                      key={ex.id}
                      to={`/exercises/${ex.id}`}
                      className="truncate text-emerald-700/80 underline-offset-2 hover:text-emerald-500 hover:underline"
                    >
                      {isZh ? ex.name : (ex.name_en || ex.name)}
                    </Link>
                  ))}
                </div>
              </div>
            );
          })}
        </div>

        {(arch.training_bias || arch.diet_bias) && (
          <div className="flex flex-wrap gap-1">
            {arch.training_bias && (
              <span className="flex items-center gap-1 text-[10px] text-orange-600/80">
                <Flame className="size-3" />
                {arch.training_bias}
              </span>
            )}
            {arch.diet_bias && (
              <span className="flex items-center gap-1 text-[10px] text-lime-700/80">
                <Salad className="size-3" />
                {arch.diet_bias}
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function ExerciseGroupPage() {
  const { isZh } = useLanguage();
  const [groups, setGroups] = useState<GoalExerciseGroupCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .get<GoalGroupsResponse>("/goal-knowledge/groups")
      .then((res) => {
        if (!cancelled) setGroups(res?.groups ?? []);
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
  }, []);

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-7xl space-y-5 p-3 sm:p-6">
          <header className="flex items-center gap-1.5 sm:gap-3">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-xl bg-emerald-100 sm:size-11 sm:rounded-2xl">
              <Dumbbell className="size-3 text-emerald-600 sm:size-5" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-[12px] font-bold text-emerald-950 sm:text-xl">
                {isZh ? "动作组" : "Exercise Groups"}
              </h1>
              <p className="truncate text-[8px] text-emerald-600/60 sm:text-sm">
                {isZh
                  ? "按身材目标查看推荐动作组与达成指标"
                  : "Recommended exercise groups by body goal"}
              </p>
            </div>
          </header>

          <ExerciseTabs />

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : groups.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-16 text-center text-emerald-600/50">
              <Dumbbell className="size-8 text-emerald-300" />
              <p className="text-sm">
                {isZh ? "暂无动作组数据" : "No exercise groups yet"}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-2 sm:gap-3">
              {groups.map((g) => (
                <GroupCard key={`${g.key}_${g.gender}`} arch={g} />
              ))}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
