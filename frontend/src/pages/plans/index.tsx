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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  RefreshCw,
  UtensilsCrossed,
} from "lucide-react";
import { api } from "@/lib/api";
import { showError } from "@/lib/toast";
import { cn } from "@/lib/utils";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CheckinCalendar } from "./checkin-calendar";
import { DayDetailDialog } from "./day-detail-dialog";
import { DietPlanCard } from "./diet-plan-card";
import { NutritionOverview } from "./nutrition-overview";
import { SyncPlanDialog } from "./sync-plan-dialog";
import {
  dayNames,
  parseDateLocal,
  dateToDow,
  type CalMode,
  type PlanDay,
  type PlanDetail,
  type PlanExercise,
  type CheckinItem,
  type CheckinExerciseItem,
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
  const [editingExerciseId, setEditingExerciseId] = useState<string | null>(null);
  const [checkinLoading, setCheckinLoading] = useState<string | null>(null);
  const [calMode, setCalMode] = useState<CalMode>("exercise");
  const [syncDialogOpen, setSyncDialogOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<"training" | "diet">("training");
  const [deleteDayTarget, setDeleteDayTarget] = useState<string | null>(null);

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
      api.get<{ items: CheckinItem[] }>("/checkins?size=100").catch(() => null),
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

  const selectedCheckin = checkins.find((c) => c.date === exDateStr) ?? null;
  const completedPdeIds = new Set(
    (selectedCheckin?.exercises ?? [])
      .map((e) => e.plan_day_exercise_id)
      .filter((id): id is string => id !== null),
  );
  const isFutureExDate = exDateStr > todayStr;

  const openDayDetail = (day: PlanDay, exerciseId: string | null = null) => {
    setSelectedDay(day);
    setEditingExerciseId(exerciseId);
    setDayDialogOpen(true);
  };

  const deleteTrainingDay = async (dayId: string) => {
    try {
      const updated = await api.delete<PlanDetail>(`/plans/days/${dayId}`);
      setActivePlan(updated);
      setDeleteDayTarget(null);
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

  const refreshCheckins = async () => {
    const [checkinRes, streakRes] = await Promise.all([
      api.get<{ items: CheckinItem[] }>("/checkins?size=100").catch(() => null),
      api.get<{ current_streak: number }>("/checkins/streak").catch(() => null),
    ]);
    if (checkinRes?.items) setCheckins(checkinRes.items);
    if (streakRes) setStreak(streakRes.current_streak);
  };

  const entryFromCheckinRow = (e: CheckinExerciseItem) => ({
    exercise_id: e.exercise_id,
    custom_name: e.custom_name ?? null,
    plan_day_exercise_id: e.plan_day_exercise_id,
    sets_done: e.sets_done,
    reps_done: e.reps_done,
    weight_kg: e.weight_kg,
    duration_min: e.duration_min,
    distance_km: e.distance_km,
  });

  const entryFromPlanExercise = (ex: PlanExercise) => ({
    exercise_id: ex.exercise_id,
    custom_name: ex.exercise_id ? null : (ex.custom_name ?? ex.exercise_name),
    plan_day_exercise_id: ex.id,
    sets_done: ex.sets,
    reps_done: ex.reps,
    weight_kg: ex.weight_kg,
    duration_min: ex.duration_min ?? null,
    distance_km: ex.distance_km ?? null,
  });

  const toggleExercise = async (ex: PlanExercise) => {
    if (!exDay || isFutureExDate || checkinLoading) return;
    setCheckinLoading(ex.id);
    try {
      const current = selectedCheckin?.exercises ?? [];
      const isChecked = current.some((e) => e.plan_day_exercise_id === ex.id);
      const remaining = current
        .filter((e) => e.plan_day_exercise_id !== ex.id)
        .map(entryFromCheckinRow);
      const nextExercises = isChecked ? remaining : [...remaining, entryFromPlanExercise(ex)];

      if (nextExercises.length === 0 && selectedCheckin) {
        await api.delete(`/checkins/${selectedCheckin.id}`);
      } else if (selectedCheckin) {
        await api.put(`/checkins/${selectedCheckin.id}`, { exercises: nextExercises });
      } else {
        await api.post("/checkins", {
          date: exDateStr,
          plan_day_id: exDay.id,
          exercises: nextExercises,
        });
      }
      await refreshCheckins();
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setCheckinLoading(null);
    }
  };

  const completeAll = async () => {
    if (!exDay || isFutureExDate || checkinLoading) return;
    setCheckinLoading("all");
    try {
      const exercises = exDay.exercises.map(entryFromPlanExercise);
      await api.post("/checkins", {
        date: exDateStr,
        plan_day_id: exDay.id,
        duration_min: Math.max(15, exDay.exercises.length * 5),
        exercises,
      });
      await refreshCheckins();
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

  const renderTrainingCard = () => (
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
            <Button
              variant="ghost"
              size="sm"
              className="text-emerald-600 hover:bg-emerald-50"
              onClick={() => setSyncDialogOpen(true)}
              disabled={!activePlan}
            >
              <RefreshCw className="mr-1 size-4" />
              同步计划
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
            {exDay.exercises.length > 0 && (
              <p className="text-xs font-medium text-emerald-600/70">
                已完成 {exDay.exercises.filter((ex) => completedPdeIds.has(ex.id)).length}
                /{exDay.exercises.length}
              </p>
            )}
            <div className="space-y-1.5">
              {exDay.exercises.length === 0 ? (
                <p className="text-xs text-emerald-600/50">暂无动作，点击编辑添加</p>
              ) : (
                [...exDay.exercises]
                  .sort((a, b) => a.sort_order - b.sort_order)
                  .map((ex) => {
                    const checked = completedPdeIds.has(ex.id);
                    const isCardio = ex.exercise_type === "cardio";
                    return (
                      <div
                        key={ex.id}
                        className="flex cursor-pointer items-center justify-between gap-2 rounded-lg bg-emerald-50/40 px-3 py-2 text-sm transition-colors hover:bg-emerald-100/50"
                        title="点击编辑该动作"
                        onClick={() => openDayDetail(exDay, ex.id)}
                      >
                        <div className="flex min-w-0 items-center gap-2">
                          <input
                            type="checkbox"
                            checked={checked}
                            disabled={isFutureExDate || checkinLoading !== null}
                            onClick={(e) => e.stopPropagation()}
                            onChange={() => toggleExercise(ex)}
                            className="size-4 shrink-0 cursor-pointer accent-emerald-600"
                          />
                          <span
                            className={cn(
                              "truncate font-medium",
                              checked
                                ? "text-emerald-400 line-through"
                                : "text-emerald-900",
                            )}
                          >
                            {ex.exercise_name ?? "未知动作"}
                          </span>
                        </div>
                        <span className="shrink-0 tabular-nums text-emerald-600/70">
                          {isCardio
                            ? `${ex.duration_min ?? 0} 分钟${ex.distance_km ? ` · ${ex.distance_km} km` : ""}`
                            : `${ex.sets ?? "-"} 组 × ${ex.reps ?? "-"} 次${ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}`}
                        </span>
                      </div>
                    );
                  })
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
              {selectedCheckin ? (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-emerald-600"
                  disabled
                >
                  <CheckCircle className="mr-1 size-3.5" />
                  已打卡
                </Button>
              ) : (
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-emerald-600 hover:bg-orange-50 hover:text-orange-600"
                  onClick={completeAll}
                  disabled={isFutureExDate || checkinLoading !== null}
                >
                  {checkinLoading === "all" ? (
                    <Loader2 className="mr-1 size-3.5 animate-spin" />
                  ) : (
                    <CheckCircle className="mr-1 size-3.5" />
                  )}
                  一键全部完成
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                className="ml-auto text-red-300 hover:text-red-600"
                onClick={() => setDeleteDayTarget(exDay.id)}
              >
                <Trash2 className="size-3.5" />
              </Button>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );

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
              {/* 移动端 Tabs：训练 / 饮食 */}
              <div className="lg:hidden">
                <Tabs
                  value={mobileTab}
                  onValueChange={(v) => setMobileTab(v as "training" | "diet")}
                >
                  <TabsList className="w-full bg-emerald-50">
                    <TabsTrigger value="training" className="flex-1">
                      <Dumbbell className="mr-1.5 size-3.5" />
                      训练
                    </TabsTrigger>
                    <TabsTrigger value="diet" className="flex-1">
                      <UtensilsCrossed className="mr-1.5 size-3.5" />
                      饮食
                    </TabsTrigger>
                  </TabsList>
                </Tabs>
                <div className="mt-4 space-y-6">
                  {mobileTab === "training" ? (
                    <>
                      <CheckinCalendar
                        mode="exercise"
                        onModeChange={setCalMode}
                        selectedDate={exDate}
                        onPickDate={pickExerciseDate}
                        checkinDates={checkinDates}
                        streak={streak}
                        dietDayCalories={dietDayCalories}
                        dietTargetCalories={dietPlan?.target_calories ?? null}
                      />
                      {renderTrainingCard()}
                    </>
                  ) : (
                    <>
                      <NutritionOverview
                        meals={dietDay?.meals ?? []}
                        settings={settings}
                        dateLabel={dietDateLabel}
                      />
                      <DietPlanCard
                        dietPlan={dietPlan}
                        dayOfWeek={dietDow}
                        selectedDateLabel={dietDateLabel}
                        settings={settings}
                        onDietPlanUpdated={(plan) => setDietPlan(plan)}
                        onSettingsUpdated={(s) => setSettings(s)}
                      />
                    </>
                  )}
                </div>
              </div>

              {/* 桌面端双栏 */}
              <div className="hidden space-y-6 lg:block">
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
                  {renderTrainingCard()}
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
            </div>
          )}
        </div>
      </div>

      <DayDetailDialog
        day={selectedDay}
        open={dayDialogOpen}
        initialEditingExerciseId={editingExerciseId}
        onClose={() => setDayDialogOpen(false)}
        onPlanUpdated={(plan) => {
          setActivePlan(plan);
          const updatedDay = plan.days.find((d) => d.id === selectedDay?.id);
          if (updatedDay) setSelectedDay(updatedDay);
        }}
      />

      <Dialog open={deleteDayTarget !== null} onOpenChange={(open) => !open && setDeleteDayTarget(null)}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>删除训练日</DialogTitle>
            <DialogDescription>
              确定删除该训练日吗？该日安排的动作将一并移除，此操作不可撤销。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDayTarget(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteDayTarget && deleteTrainingDay(deleteDayTarget)}
            >
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <SyncPlanDialog
        activePlan={activePlan}
        targetDayOfWeek={exDow}
        open={syncDialogOpen}
        onClose={() => setSyncDialogOpen(false)}
        onPlanUpdated={setActivePlan}
      />
    </AppLayout>
  );
}
