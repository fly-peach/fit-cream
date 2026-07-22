import { useEffect, useState } from "react";
import { AppLayout } from "@/components/app-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dumbbell,
  Loader2,
  Trash2,
  CalendarDays,
  Clock,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

interface PlanExercise {
  id: string;
  exercise_name: string | null;
  sets: number;
  reps: number;
  weight_kg: number | null;
  sort_order: number;
}

interface PlanDay {
  id: string;
  day_of_week: number;
  focus: string | null;
  rest_seconds: number;
  exercises: PlanExercise[];
}

interface PlanDetail {
  id: string;
  name: string;
  goal: string | null;
  difficulty: string | null;
  weeks: number | null;
  status: string;
  days: PlanDay[];
}

interface PlanListItem {
  id: string;
  name: string;
  goal: string | null;
  difficulty: string | null;
  weeks: number | null;
  status: string;
}

const dayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

const goalLabels: Record<string, string> = {
  lose_fat: "减脂塑形",
  gain_muscle: "增肌增重",
  maintain: "保持健康",
  improve_health: "改善体质",
};

const difficultyLabels: Record<string, string> = {
  beginner: "入门",
  intermediate: "进阶",
  advanced: "高级",
};

const statusLabels: Record<string, string> = {
  active: "进行中",
  archived: "已归档",
  completed: "已完成",
};

export default function PlansPage() {
  const [plans, setPlans] = useState<PlanListItem[]>([]);
  const [activePlan, setActivePlan] = useState<PlanDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<PlanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadPlans = async () => {
    try {
      const res = await api.get<{ items: PlanListItem[] }>("/plans");
      setPlans(res.items || []);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  useEffect(() => {
    Promise.all([
      api.get<PlanDetail | null>("/plans/active").catch(() => null),
      loadPlans(),
    ])
      .then(([active]) => setActivePlan(active))
      .finally(() => setLoading(false));
  }, []);

  const openPlan = async (id: string) => {
    setSelectedId(id);
    try {
      const detail = await api.get<PlanDetail>(`/plans/${id}`);
      setSelectedPlan(detail);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定删除该训练计划？")) return;
    try {
      await api.delete(`/plans/${id}`);
      setPlans((prev) => prev.filter((p) => p.id !== id));
      if (selectedId === id) {
        setSelectedId(null);
        setSelectedPlan(null);
      }
      if (activePlan?.id === id) setActivePlan(null);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const displayPlan = selectedPlan ?? activePlan;

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-6xl space-y-6 p-6">
          <header className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-100">
              <Dumbbell className="size-5 text-emerald-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-emerald-950">训练计划</h1>
              <p className="text-sm text-emerald-600/60">查看与管理你的专属训练计划</p>
            </div>
          </header>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : (
            <div className="grid gap-6 lg:grid-cols-3">
              {/* 计划列表 */}
              <div className="space-y-3 lg:col-span-1">
                <h2 className="text-sm font-semibold text-emerald-800">全部计划</h2>
                {plans.length === 0 && (
                  <Card className="border-dashed border-emerald-200">
                    <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
                      <Sparkles className="size-6 text-emerald-300" />
                      <p className="text-sm text-emerald-600/60">
                        暂无计划，去 AI 教练处生成一个吧
                      </p>
                    </CardContent>
                  </Card>
                )}
                {plans.map((plan) => (
                  <Card
                    key={plan.id}
                    onClick={() => openPlan(plan.id)}
                    className={cn(
                      "cursor-pointer border-emerald-100 bg-white/80 transition-all hover:border-emerald-300 hover:shadow-sm",
                      (selectedId === plan.id ||
                        (!selectedId && activePlan?.id === plan.id)) &&
                        "border-emerald-400 ring-1 ring-emerald-300"
                    )}
                  >
                    <CardContent className="flex items-center justify-between p-4">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="truncate font-medium text-emerald-950">{plan.name}</p>
                          {activePlan?.id === plan.id && (
                            <Badge className="border-emerald-200 bg-emerald-100 text-emerald-700">
                              进行中
                            </Badge>
                          )}
                        </div>
                        <div className="mt-1 flex flex-wrap gap-1.5 text-xs text-emerald-600/60">
                          {plan.goal && <span>{goalLabels[plan.goal] ?? plan.goal}</span>}
                          {plan.difficulty && (
                            <span>· {difficultyLabels[plan.difficulty] ?? plan.difficulty}</span>
                          )}
                          {plan.weeks && <span>· {plan.weeks} 周</span>}
                        </div>
                      </div>
                      <ChevronRight className="size-4 shrink-0 text-emerald-300" />
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* 计划详情 */}
              <div className="lg:col-span-2">
                {displayPlan ? (
                  <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div>
                          <CardTitle className="text-lg font-semibold text-emerald-950">
                            {displayPlan.name}
                          </CardTitle>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {displayPlan.goal && (
                              <Badge variant="secondary" className="border-emerald-200 bg-emerald-50 text-emerald-700">
                                {goalLabels[displayPlan.goal] ?? displayPlan.goal}
                              </Badge>
                            )}
                            {displayPlan.difficulty && (
                              <Badge variant="secondary" className="border-amber-200 bg-amber-50 text-amber-700">
                                {difficultyLabels[displayPlan.difficulty] ?? displayPlan.difficulty}
                              </Badge>
                            )}
                            <Badge variant="secondary" className="border-sky-200 bg-sky-50 text-sky-700">
                              {statusLabels[displayPlan.status] ?? displayPlan.status}
                            </Badge>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="text-emerald-400 hover:bg-red-100 hover:text-red-600"
                          onClick={() => handleDelete(displayPlan.id)}
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {displayPlan.days.length === 0 && (
                        <p className="py-6 text-center text-sm text-emerald-600/60">
                          该计划暂无训练日安排
                        </p>
                      )}
                      {[...displayPlan.days]
                        .sort((a, b) => a.day_of_week - b.day_of_week)
                        .map((day) => (
                          <div
                            key={day.id}
                            className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-4"
                          >
                            <div className="mb-3 flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
                                  {dayNames[day.day_of_week - 1]}
                                </span>
                                <span className="font-medium text-emerald-900">
                                  {day.focus || "综合训练"}
                                </span>
                              </div>
                              <span className="flex items-center gap-1 text-xs text-emerald-600/60">
                                <Clock className="size-3" />
                                休息 {day.rest_seconds}s
                              </span>
                            </div>
                            {day.exercises.length === 0 ? (
                              <p className="text-xs text-emerald-600/50">休息日</p>
                            ) : (
                              <div className="space-y-1.5">
                                {[...day.exercises]
                                  .sort((a, b) => a.sort_order - b.sort_order)
                                  .map((ex) => (
                                    <div
                                      key={ex.id}
                                      className="flex items-center justify-between rounded-lg bg-white px-3 py-2 text-sm"
                                    >
                                      <span className="font-medium text-emerald-900">
                                        {ex.exercise_name ?? "未知动作"}
                                      </span>
                                      <span className="tabular-nums text-emerald-600/70">
                                        {ex.sets} 组 × {ex.reps} 次
                                        {ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}
                                      </span>
                                    </div>
                                  ))}
                              </div>
                            )}
                          </div>
                        ))}
                    </CardContent>
                  </Card>
                ) : (
                  <Card className="flex h-full min-h-64 items-center justify-center border-dashed border-emerald-200">
                    <CardContent className="flex flex-col items-center gap-3 text-center">
                      <CalendarDays className="size-8 text-emerald-300" />
                      <p className="text-sm text-emerald-600/60">
                        选择左侧计划查看详情，或让 AI 教练为你生成计划
                      </p>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}