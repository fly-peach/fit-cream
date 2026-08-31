/**
 * 动作组页 /exercises/exercise-group
 *
 * 身材原型卡片网格（一行 3 个）：仅展示身材图 + 名称 + tagline，
 * 点击进详情页 /exercises/exercise-group/:key（桌面 Web 新标签页）。
 * 数据来自 GET /goal-knowledge/groups（按当前用户性别取行）。
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Dumbbell, ImageIcon } from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { ExerciseTabs } from "@/components/exercise-tabs";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { resolveStaticUrl } from "@/lib/api-url";
import { openDetail } from "@/lib/nav";
import { useLanguage } from "@/lib/language-context";
import type { GoalExerciseGroupCard, GoalGroupsResponse } from "@/types/goal";

function GroupCard({ arch }: { arch: GoalExerciseGroupCard }) {
  const navigate = useNavigate();
  return (
    <Card
      onClick={() => openDetail(navigate, `/exercises/exercise-group/${arch.key}`)}
      className="group flex h-full cursor-pointer flex-col overflow-hidden border-emerald-100 bg-white/80 transition-all hover:border-emerald-300 hover:shadow-md"
    >
      <CardContent className="flex flex-1 flex-col gap-1.5 p-2">
        <div className="relative aspect-[3/4] w-full overflow-hidden rounded-lg bg-emerald-50">
          {arch.image ? (
            <img
              src={resolveStaticUrl(arch.image)}
              alt={arch.name}
              loading="lazy"
              className="absolute inset-0 size-full object-cover transition-transform duration-300 group-hover:scale-[1.03]"
            />
          ) : (
            <div className="flex size-full items-center justify-center text-emerald-200">
              <ImageIcon className="size-8" />
            </div>
          )}
        </div>
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-emerald-950">{arch.name}</h3>
          {arch.tagline && (
            <p className="line-clamp-1 text-xs text-emerald-600/70">{arch.tagline}</p>
          )}
        </div>
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
