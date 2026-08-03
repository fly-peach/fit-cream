import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import { useNavigate, useParams } from "react-router-dom";
import { AppLayout } from "@/components/app-layout";
import { MetadataPreview } from "@/components/metadata-editor";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dumbbell,
  Loader2,
  Trash2,
  Clock,
  Pencil,
  Plus,
  CheckCircle,
} from "lucide-react";
import { api } from "@/lib/api";
import { showError } from "@/lib/toast";
import { CheckinCalendar } from "./checkin-calendar";
import { DayDetailDialog } from "./day-detail-dialog";
import { DietPlanCard } from "./diet-plan-card";
import { NutritionOverview } from "./nutrition-overview";
import {
  dayNames,
  parseDateLocal,
  dateToDow,
  type CalMode,
  type PlanDay,
  type PlanDetail,
  type CheckinItem,
  type DietPlanDetail,
  type UserSettings,
} from "./types";

const goalOptions = [
  { value: "lose_fat", label: "减脂塑形" },
  { value: "gain_muscle", label: "增肌增重" },
  { value: "maintain", label: "保持健康" },
  { value: "improve_health", label: "改善体质" },
];

const difficultyOptions = [
  { value: "beginner", label: "初级" },
  { value: "intermediate", label: "中级" },
  { value: "advanced", label: "高级" },
];

export default function PlansPage() {
  const navigate = useNavigate();
  const { exSegment, dtSegment } = useParams();

  const exParam = exSegment?.startsWith("exercise-plan-date=")
    ? exSegment.slice("exercise-plan-date=".length)
    : undefined;
  const dietParam = dtSegment?.startsWith("diet-plan-date=")
    ? dtSegment.slice("diet-plan-date=".length)
    : undefined;

  const todayStr = format(new Date(), "yyyy-MM-dd");
  const exDateStr = exParam ?? todayStr;
  const dietDateStr = dietParam ?? todayStr;
  const exDate = parseDateLocal(exDateStr);
  const dietDate = parseDateLocal(dietDateStr);

  const [activePlan, setActivePlan] = useState<PlanDetail | null>(null);
  const [checkins, setCheckins] = useState<CheckinItem[]>([]);
  const [streak, setStreak] = useState(0);
  const [dietPlan, setDietPlan] = useState<DietPlanDetail | null>(null);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [dayDialogOpen, setDayDialogOpen] = useState(false);
  const [selectedDay, setSelectedDay] = useState<PlanDay | null>(null);
  const [checkinLoading, setCheckinLoading] = useState<string | null>(null);
  const [calMode, setCalMode] = useState<CalMode>("exercise");

  // 创建首个训练计划的内联表单状态
  const [creatingPlan, setCreatingPlan] = useState(false);
  const [newPlanName, setNewPlanName] = useState("我的训练计划");
  const [newPlanGoal, setNewPlanGoal] = useState<string>("");
  const [newPlanDifficulty, setNewPlanDifficulty] = useState("beginner");
  const [newPlanWeeks, setNewPlanWeeks] = useState("");
  const [planCreating, setPlanCreating] = useState(false);

  useEffect(() => {
    if (!exParam || !dietParam) {
      const t = format(new Date(), "yyyy-MM-dd");
      navigate(
        `/plans/exercise-plan-date=${exParam ?? t}/diet-plan-date=${dietParam ?? t}`,
        { replace: true },
      );
    }
  }, [exParam, dietParam, navigate]);

  useEffect(() => {
    Promise.all([
      api.get<PlanDetail | null>("/plans/active").catch(() => null),
      api.get<{ items: CheckinItem[] }>("/checkins?limit=200").catch(() => null),
      api.get<{ current_streak: number }>("/checkins/streak").catch(() => null),
      api.get<DietPlanDetail | null>("/diet-plans/active").catch(() => null),
      api.get<UserSettings>("/users/settings").catch(() => null),
    ])
      .then(([active, checkinRes, streakRes, diet, userSettings]) => {
        setActivePlan(active);
        if (checkinRes?.items) setCheckins(checkinRes.items);
        if (streakRes) setStreak(streakRes.current_streak);
        setDietPlan(diet);
        setSettings(userSettings);
      })
      .finally(() => setLoading(false));
  }, []);

  const checkinDates = useMemo(() => new Set(checkins.map((c) => c.date)), [checkins]);

  const exDow = dateToDow(exDate);
  const dietDow = dateToDow(dietDate);
  const exDay = activePlan?.days.find((d) => d.day_of_week === exDow) ?? null;
  const dietDay = dietPlan?.days.find((d) => d.day_of_week === dietDow) ?? null;
  const dietDayCalories = dietDay?.meals.reduce((s, m) => s + (m.calories ?? 0), 0) ?? 0;

  const openDayDetail = (day: PlanDay) => {
    setSelectedDay(day);
    setDayDialogOpen(true);
  };

  const deleteTrainingDay = async (dayId: string) => {
    if (!confirm("确定删除该训练日？")) return;
    try {
      const updated = await api.delete<PlanDetail>(`/plans/days/${dayId}`);
      setActivePlan(updated);
    } catch (e) {
      showError((e as Error).message);
    }
  };

  const addTrainingDayFor = async (dow: number) => {
    if (!activePlan?.id) return;
    try {
      const updated = await api.post<PlanDetail>(`/plans/${activePlan.id}/days`, {
        day_of_week: dow,
        focus: `${dayNames[dow - 1]}训练`,
        rest_seconds: 60,
        exercises: [],
      });
      setActivePlan(updated);
    } catch (e) {
      showError((e as Error).message);
    }
  };

  const createTrainingPlan = async () => {
    setPlanCreating(true);
    try {
      const weeksNum = newPlanWeeks ? parseInt(newPlanWeeks, 10) : 0;
      const created = await api.post<PlanDetail>("/plans", {
        name: newPlanName.trim() || "我的训练计划",
        goal: newPlanGoal || null,
        difficulty: newPlanDifficulty,
        weeks: weeksNum >= 1 && weeksNum <= 52 ? weeksNum : null,
        days: [],
      });
      setActivePlan(created);
      setCreatingPlan(false);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setPlanCreating(false);
    }
  };

  const checkinDay = async (day: PlanDay) => {
    setCheckinLoading(day.id);
    try {
      const duration = Math.max(15, day.exercises.length * 5);
      await api.post("/checkins", { date: format(new Date(), "yyyy-MM-dd"), duration_min: duration });
      const streakRes = await api.get<{ current_streak: number }>("/checkins/streak");
      const checkinRes = await api.get<{ items: CheckinItem[] }>("/checkins?limit=200");
      setStreak(streakRes.current_streak);
      if (checkinRes?.items) setCheckins(checkinRes.items);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setCheckinLoading(null);
    }
  };

  const pickExerciseDate = (d: Date) => {
    navigate(`/plans/exercise-plan-date=${format(d, "yyyy-MM-dd")}/diet-plan-date=${dietDateStr}`);
  };
  const pickDietDate = (d: Date) => {
    navigate(`/plans/exercise-plan-date=${exDateStr}/diet-plan-date=${format(d, "yyyy-MM-dd")}`);
  };

  const exDateLabel = `${format(exDate, "M月d日", { locale: zhCN })} · ${dayNames[exDow - 1]}`;
  const dietDateLabel = `${format(dietDate, "M月d日", { locale: zhCN })} · ${dayNames[dietDow - 1]}`;

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-7xl space-y-6 p-6">
          <header className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-100">
              <Dumbbell className="size-5 text-emerald-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-emerald-950">训练与饮食计划</h1>
              <p className="text-sm text-emerald-600/60">按日期查看与管理你的训练和饮食安排</p>
            </div>
          </header>

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : (
            <div className="space-y-6">
              <div className="grid items-start gap-6 lg:grid-cols-2">
                <CheckinCalendar
                  mode={calMode}
                  onModeChange={setCalMode}
                  selectedDate={calMode === "exercise" ? exDate : dietDate}
                  onPickDate={calMode === "exercise" ? pickExerciseDate : pickDietDate}
                  checkinDates={checkinDates}
                  streak={streak}
                  dietDayCalories={dietDayCalories}
                  dietTargetCalories={dietPlan?.target_calories ?? null}
                />
                <NutritionOverview
                  meals={dietDay?.meals ?? []}
                  settings={settings}
                  dateLabel={dietDateLabel}
                />
              </div>

              <div className="grid gap-6 lg:grid-cols-2">
                <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                  <CardHeader>
                    <div className="flex items-start justify-between">
                      <div>
                        <CardTitle className="text-lg font-semibold text-emerald-950">
                          当日训练
                        </CardTitle>
                        <p className="mt-1 text-xs text-emerald-600/70">
                          {exDateLabel}
                          {activePlan ? ` · ${activePlan.name}` : ""}
                        </p>
                      </div>
                      {exDay && (
                        <Button
                          variant="ghost"
                          size="icon"
                          title="编辑训练日"
                          className="text-emerald-400 hover:text-emerald-600"
                          onClick={() => openDayDetail(exDay)}
                        >
                          <Pencil className="size-4" />
                        </Button>
                      )}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {!activePlan ? (
                      <div className="flex flex-col items-center gap-3 py-6 text-center">
                        <Dumbbell className="size-8 text-emerald-300" />
                        <p className="text-sm text-emerald-600/60">
                          暂无训练计划，可手动创建或让 AI 教练为你生成
                        </p>
                        {!creatingPlan ? (
                          <Button
                            variant="outline"
                            size="sm"
                            className="border-emerald-200 text-emerald-700"
                            onClick={() => setCreatingPlan(true)}
                          >
                            <Plus className="mr-1 size-4" />
                            创建训练计划
                          </Button>
                        ) : (
                          <div className="w-full max-w-sm space-y-2.5 rounded-lg border border-emerald-100 bg-emerald-50/30 p-3 text-left">
                            <div className="space-y-1">
                              <label className="text-xs font-medium text-emerald-700">计划名称</label>
                              <Input
                                value={newPlanName}
                                onChange={(e) => setNewPlanName(e.target.value)}
                                placeholder="我的训练计划"
                                className="border-emerald-200 focus-visible:ring-emerald-400"
                              />
                            </div>
                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <label className="text-xs font-medium text-emerald-700">健身目标</label>
                                <Select
                                  value={newPlanGoal}
                                  onValueChange={(v) => setNewPlanGoal(v ?? "")}
                                >
                                  <SelectTrigger className="border-emerald-200 focus:ring-emerald-400">
                                    <SelectValue placeholder="不指定">
                                      {goalOptions.find((o) => o.value === newPlanGoal)?.label}
                                    </SelectValue>
                                  </SelectTrigger>
                                  <SelectContent>
                                    {goalOptions.map((o) => (
                                      <SelectItem key={o.value} value={o.value}>
                                        {o.label}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                              <div className="space-y-1">
                                <label className="text-xs font-medium text-emerald-700">难度</label>
                                <Select
                                  value={newPlanDifficulty}
                                  onValueChange={(v) => setNewPlanDifficulty(v ?? "beginner")}
                                >
                                  <SelectTrigger className="border-emerald-200 focus:ring-emerald-400">
                                    <SelectValue>
                                      {difficultyOptions.find((o) => o.value === newPlanDifficulty)?.label}
                                    </SelectValue>
                                  </SelectTrigger>
                                  <SelectContent>
                                    {difficultyOptions.map((o) => (
                                      <SelectItem key={o.value} value={o.value}>
                                        {o.label}
                                      </SelectItem>
                                    ))}
                                  </SelectContent>
                                </Select>
                              </div>
                            </div>
                            <div className="space-y-1">
                              <label className="text-xs font-medium text-emerald-700">周期（周，可选）</label>
                              <Input
                                type="number"
                                min={1}
                                max={52}
                                value={newPlanWeeks}
                                onChange={(e) => setNewPlanWeeks(e.target.value)}
                                placeholder="如 4"
                                className="border-emerald-200 focus-visible:ring-emerald-400"
                              />
                            </div>
                            <div className="flex items-center gap-2 pt-1">
                              <Button
                                size="sm"
                                className="bg-emerald-600 text-white hover:bg-emerald-700"
                                onClick={createTrainingPlan}
                                disabled={planCreating}
                              >
                                {planCreating ? (
                                  <Loader2 className="mr-1 size-3.5 animate-spin" />
                                ) : (
                                  <Plus className="mr-1 size-3.5" />
                                )}
                                创建
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                className="text-emerald-600"
                                onClick={() => setCreatingPlan(false)}
                                disabled={planCreating}
                              >
                                取消
                              </Button>
                            </div>
                          </div>
                        )}
                      </div>
                    ) : !exDay ? (
                      <div className="flex flex-col items-center gap-2 py-6 text-center">
                        <p className="text-sm text-emerald-600/60">
                          {dayNames[exDow - 1]}暂无训练安排
                        </p>
                        <Button
                          variant="outline"
                          size="sm"
                          className="border-emerald-200 text-emerald-700"
                          onClick={() => addTrainingDayFor(exDow)}
                        >
                          <Plus className="mr-1 size-4" />
                          添加{dayNames[exDow - 1]}训练日
                        </Button>
                      </div>
                    ) : (
                      <>
                        <div className="flex items-center gap-2">
                          <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
                            {dayNames[exDay.day_of_week - 1]}
                          </span>
                          <span className="font-medium text-emerald-900">
                            {exDay.focus || "综合训练"}
                          </span>
                        </div>
                        <div className="flex items-center gap-1 text-xs text-emerald-600/60">
                          <Clock className="size-3" />
                          休息 {exDay.rest_seconds}s
                        </div>
                        <MetadataPreview value={exDay.metadata_} />
                        <div className="space-y-1.5">
                          {exDay.exercises.length === 0 ? (
                            <p className="text-xs text-emerald-600/50">暂无动作，点击编辑添加</p>
                          ) : (
                            [...exDay.exercises]
                              .sort((a, b) => a.sort_order - b.sort_order)
                              .map((ex) => (
                                <div
                                  key={ex.id}
                                  className="flex items-center justify-between rounded-lg bg-emerald-50/40 px-3 py-2 text-sm"
                                >
                                  <span className="font-medium text-emerald-900">
                                    {ex.exercise_name ?? "未知动作"}
                                  </span>
                                  <span className="tabular-nums text-emerald-600/70">
                                    {ex.sets} 组 × {ex.reps} 次
                                    {ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}
                                  </span>
                                </div>
                              ))
                          )}
                        </div>
                        <div className="flex items-center gap-2 pt-1">
                          <Button
                            size="sm"
                            variant="outline"
                            className="border-emerald-200 text-emerald-700"
                            onClick={() => openDayDetail(exDay)}
                          >
                            <Pencil className="mr-1 size-3.5" />
                            编辑动作
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="text-emerald-600 hover:bg-orange-50 hover:text-orange-600"
                            onClick={() => checkinDay(exDay)}
                            disabled={checkinLoading === exDay.id}
                          >
                            {checkinLoading === exDay.id ? (
                              <Loader2 className="mr-1 size-3.5 animate-spin" />
                            ) : (
                              <CheckCircle className="mr-1 size-3.5" />
                            )}
                            打卡
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="ml-auto text-red-300 hover:text-red-600"
                            onClick={() => deleteTrainingDay(exDay.id)}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>

                <DietPlanCard
                  dietPlan={dietPlan}
                  dayOfWeek={dietDow}
                  selectedDateLabel={dietDateLabel}
                  settings={settings}
                  onDietPlanUpdated={(plan) => setDietPlan(plan)}
                  onSettingsUpdated={(s) => setSettings(s)}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      <DayDetailDialog
        day={selectedDay}
        open={dayDialogOpen}
        onClose={() => setDayDialogOpen(false)}
        onPlanUpdated={(plan) => {
          setActivePlan(plan);
          const updatedDay = plan.days.find((d) => d.id === selectedDay?.id);
          if (updatedDay) setSelectedDay(updatedDay);
        }}
      />
    </AppLayout>
  );
}
