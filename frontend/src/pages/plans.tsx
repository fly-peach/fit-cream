import { useEffect, useMemo, useState } from "react";
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
  isSameDay,
  addMonths,
  subMonths,
  startOfWeek,
  endOfWeek,
  isToday,
  isBefore,
} from "date-fns";
import { zhCN } from "date-fns/locale";
import { AppLayout } from "@/components/app-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
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
  CalendarDays,
  Clock,
  ChevronRight,
  ChevronLeft,
  Sparkles,
  Flame,
  UtensilsCrossed,
  Pencil,
  Plus,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

// ============ Types ============

interface PlanExercise {
  id: string;
  exercise_id: string;
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

interface CheckinItem {
  id: string;
  date: string;
  duration_min: number;
}

interface DietMeal {
  id: string;
  meal_type: string;
  food_name: string;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  portion: string | null;
  sort_order: number;
}

interface DietDay {
  id: string;
  day_of_week: number;
  focus: string | null;
  meals: DietMeal[];
}

interface DietPlanDetail {
  id: string;
  name: string;
  target_calories: number | null;
  goal: string | null;
  status: string;
  days: DietDay[];
}

// ============ Constants ============

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

const mealTypeLabels: Record<string, string> = {
  breakfast: "早餐",
  lunch: "午餐",
  dinner: "晚餐",
  snack: "加餐",
};

const mealTypeColors: Record<string, string> = {
  breakfast: "bg-amber-100 text-amber-700",
  lunch: "bg-emerald-100 text-emerald-700",
  dinner: "bg-sky-100 text-sky-700",
  snack: "bg-purple-100 text-purple-700",
};

// ============ 打卡日历组件 ============

function CheckinCalendar({
  checkinDates,
  streak,
}: {
  checkinDates: Set<string>;
  streak: number;
}) {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(new Date());
  const today = new Date();

  const calendarDays = useMemo(() => {
    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
    const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
    return eachDayOfInterval({ start: calStart, end: calEnd });
  }, [currentMonth]);

  const monthCheckins = useMemo(() => {
    return calendarDays.filter(
      (d) => isSameMonth(d, currentMonth) && checkinDates.has(format(d, "yyyy-MM-dd"))
    ).length;
  }, [calendarDays, currentMonth, checkinDates]);

  const selectedChecked = checkinDates.has(format(selectedDate, "yyyy-MM-dd"));

  return (
    <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-emerald-950">
            <CalendarDays className="size-4 text-emerald-500" />
            打卡日历
          </CardTitle>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="icon"
              className="size-7 text-emerald-700 hover:bg-emerald-100"
              onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
            >
              <ChevronLeft className="size-4" />
            </Button>
            <span className="min-w-20 text-center text-sm font-medium text-emerald-900">
              {format(currentMonth, "yyyy年M月", { locale: zhCN })}
            </span>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 text-emerald-700 hover:bg-emerald-100"
              onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
            >
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-2 grid grid-cols-7 text-center text-xs font-medium text-emerald-600/60">
          {["一", "二", "三", "四", "五", "六", "日"].map((d) => (
            <div key={d} className="py-1">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {calendarDays.map((day) => {
            const dateStr = format(day, "yyyy-MM-dd");
            const checked = checkinDates.has(dateStr);
            const inMonth = isSameMonth(day, currentMonth);
            const isSelected = isSameDay(day, selectedDate);
            const isFuture = isBefore(today, day) && !isSameDay(day, today);

            return (
              <button
                key={dateStr}
                onClick={() => setSelectedDate(day)}
                className={cn(
                  "relative flex size-9 items-center justify-center rounded-lg text-sm transition-all duration-150",
                  !inMonth && "text-emerald-200",
                  inMonth && !checked && !isSelected && "text-emerald-800 hover:bg-emerald-50",
                  checked && "bg-emerald-100 font-medium text-emerald-700 hover:bg-emerald-200",
                  isSelected && "ring-2 ring-emerald-400",
                  isToday(day) && "font-bold text-emerald-950",
                  isFuture && "opacity-40"
                )}
              >
                {format(day, "d")}
                {checked && (
                  <span className="absolute bottom-1 size-1 rounded-full bg-emerald-500" />
                )}
              </button>
            );
          })}
        </div>
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between rounded-lg bg-emerald-50 px-3 py-2">
            <span className="text-xs text-emerald-700">
              {format(selectedDate, "M月d日", { locale: zhCN })}
              {selectedChecked ? (
                <span className="ml-2 font-medium text-emerald-600">✓ 已打卡</span>
              ) : (
                <span className="ml-2 text-emerald-400">未打卡</span>
              )}
            </span>
            <span className="text-xs text-emerald-700">
              本月 <span className="font-semibold text-emerald-600">{monthCheckins}</span> 天
            </span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-orange-50 px-3 py-2">
            <span className="flex items-center gap-1.5 text-xs text-orange-600">
              <Flame className="size-3.5 text-orange-500" />
              当前连续打卡
            </span>
            <span className="text-sm font-bold text-orange-600">
              {streak}
              <span className="ml-0.5 text-xs font-normal">天</span>
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// ============ 训练日详情弹窗 ============

function DayDetailDialog({
  day,
  open,
  onClose,
}: {
  day: PlanDay | null;
  open: boolean;
  onClose: () => void;
}) {
  if (!day) return null;

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-950">
            <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
              {dayNames[day.day_of_week - 1]}
            </span>
            {day.focus || "综合训练"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="flex items-center gap-2 text-sm text-emerald-600/70">
            <Clock className="size-4" />
            组间休息 {day.rest_seconds} 秒
          </div>
          {day.exercises.length === 0 ? (
            <p className="py-4 text-center text-sm text-emerald-600/50">休息日，无训练安排</p>
          ) : (
            <div className="space-y-2">
              {[...day.exercises]
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((ex, idx) => (
                  <div
                    key={ex.id}
                    className="flex items-center gap-3 rounded-lg border border-emerald-100 bg-emerald-50/50 px-4 py-3"
                  >
                    <span className="flex size-6 items-center justify-center rounded-full bg-emerald-200 text-xs font-bold text-emerald-700">
                      {idx + 1}
                    </span>
                    <div className="flex-1">
                      <p className="font-medium text-emerald-900">{ex.exercise_name ?? "未知动作"}</p>
                      <p className="text-xs text-emerald-600/60">
                        {ex.sets} 组 × {ex.reps} 次
                        {ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}
                      </p>
                    </div>
                  </div>
                ))}
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============ 饮食计划组件 ============

function DietPlanCard({ dietPlan }: { dietPlan: DietPlanDetail | null }) {
  const [selectedDay, setSelectedDay] = useState<number>(1);

  if (!dietPlan) {
    return (
      <Card className="flex h-full min-h-64 items-center justify-center border-dashed border-orange-200">
        <CardContent className="flex flex-col items-center gap-3 text-center">
          <UtensilsCrossed className="size-8 text-orange-300" />
          <p className="text-sm text-orange-600/60">
            暂无饮食计划，让 AI 教练为你定制营养方案
          </p>
        </CardContent>
      </Card>
    );
  }

  const currentDay = dietPlan.days.find((d) => d.day_of_week === selectedDay);
  const totalCalories = currentDay?.meals.reduce((sum, m) => sum + (m.calories ?? 0), 0) ?? 0;

  return (
    <Card className="border-orange-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-orange-950">
            <UtensilsCrossed className="size-4 text-orange-500" />
            {dietPlan.name}
          </CardTitle>
          {dietPlan.target_calories && (
            <Badge className="border-orange-200 bg-orange-50 text-orange-700">
              {dietPlan.target_calories} kcal/天
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* 星期选择器 */}
        <div className="flex gap-1 overflow-x-auto pb-1">
          {dayNames.map((name, idx) => {
            const dayNum = idx + 1;
            const hasMeals = dietPlan.days.some((d) => d.day_of_week === dayNum && d.meals.length > 0);
            return (
              <button
                key={dayNum}
                onClick={() => setSelectedDay(dayNum)}
                className={cn(
                  "flex-shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-all",
                  selectedDay === dayNum
                    ? "bg-orange-500 text-white shadow-sm"
                    : hasMeals
                      ? "bg-orange-100 text-orange-700 hover:bg-orange-200"
                      : "bg-gray-100 text-gray-400"
                )}
              >
                {name}
              </button>
            );
          })}
        </div>

        {/* 当日餐食 */}
        {currentDay && currentDay.meals.length > 0 ? (
          <div className="space-y-3">
            {currentDay.focus && (
              <p className="text-xs font-medium text-orange-600/70">📋 {currentDay.focus}</p>
            )}
            <div className="flex items-center justify-between rounded-lg bg-orange-50 px-3 py-2">
              <span className="text-xs text-orange-600">当日总热量</span>
              <span className="text-sm font-bold text-orange-600">{totalCalories} kcal</span>
            </div>
            {[...currentDay.meals]
              .sort((a, b) => a.sort_order - b.sort_order)
              .map((meal) => (
                <div
                  key={meal.id}
                  className="rounded-xl border border-orange-100 bg-orange-50/30 p-3"
                >
                  <div className="mb-2 flex items-center justify-between">
                    <span
                      className={cn(
                        "rounded-md px-2 py-0.5 text-xs font-medium",
                        mealTypeColors[meal.meal_type] ?? "bg-gray-100 text-gray-600"
                      )}
                    >
                      {mealTypeLabels[meal.meal_type] ?? meal.meal_type}
                    </span>
                    {meal.calories && (
                      <span className="text-xs font-medium text-orange-600">{meal.calories} kcal</span>
                    )}
                  </div>
                  <p className="font-medium text-orange-950">{meal.food_name}</p>
                  {meal.portion && (
                    <p className="mt-0.5 text-xs text-orange-600/60">份量：{meal.portion}</p>
                  )}
                  {(meal.protein_g || meal.carbs_g || meal.fat_g) && (
                    <div className="mt-2 flex gap-3 text-xs text-orange-600/70">
                      {meal.protein_g != null && <span>蛋白质 {meal.protein_g}g</span>}
                      {meal.carbs_g != null && <span>碳水 {meal.carbs_g}g</span>}
                      {meal.fat_g != null && <span>脂肪 {meal.fat_g}g</span>}
                    </div>
                  )}
                </div>
              ))}
          </div>
        ) : (
          <p className="py-6 text-center text-sm text-orange-600/50">
            当天暂无餐食安排
          </p>
        )}
      </CardContent>
    </Card>
  );
}

// ============ 主页面 ============

export default function PlansPage() {
  const [plans, setPlans] = useState<PlanListItem[]>([]);
  const [activePlan, setActivePlan] = useState<PlanDetail | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<PlanDetail | null>(null);
  const [checkins, setCheckins] = useState<CheckinItem[]>([]);
  const [streak, setStreak] = useState(0);
  const [dietPlan, setDietPlan] = useState<DietPlanDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dayDialogOpen, setDayDialogOpen] = useState(false);
  const [selectedDay, setSelectedDay] = useState<PlanDay | null>(null);

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
      api.get<{ items: CheckinItem[] }>("/checkins?limit=200").catch(() => null),
      api.get<{ current_streak: number }>("/checkins/streak").catch(() => null),
      api.get<DietPlanDetail | null>("/diet-plans/active").catch(() => null),
    ])
      .then(([active, , checkinRes, streakRes, diet]) => {
        setActivePlan(active);
        if (checkinRes?.items) setCheckins(checkinRes.items);
        if (streakRes) setStreak(streakRes.current_streak);
        setDietPlan(diet);
      })
      .finally(() => setLoading(false));
  }, []);

  const checkinDates = useMemo(() => new Set(checkins.map((c) => c.date)), [checkins]);

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

  const openDayDetail = (day: PlanDay) => {
    setSelectedDay(day);
    setDayDialogOpen(true);
  };

  const displayPlan = selectedPlan ?? activePlan;

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
              <p className="text-sm text-emerald-600/60">查看与管理你的专属训练和饮食计划</p>
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
            <div className="grid gap-6 xl:grid-cols-4">
              {/* 左栏：打卡日历 + 计划列表 */}
              <div className="space-y-6 xl:col-span-1">
                <CheckinCalendar checkinDates={checkinDates} streak={streak} />

                <div className="space-y-3">
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
              </div>

              {/* 中栏：训练计划详情 */}
              <div className="xl:col-span-2">
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
                              <Badge
                                variant="secondary"
                                className="border-emerald-200 bg-emerald-50 text-emerald-700"
                              >
                                {goalLabels[displayPlan.goal] ?? displayPlan.goal}
                              </Badge>
                            )}
                            {displayPlan.difficulty && (
                              <Badge
                                variant="secondary"
                                className="border-amber-200 bg-amber-50 text-amber-700"
                              >
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
                            onClick={() => openDayDetail(day)}
                            className="cursor-pointer rounded-xl border border-emerald-100 bg-emerald-50/40 p-4 transition-all hover:border-emerald-300 hover:shadow-sm"
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
                              <div className="flex items-center gap-2">
                                <span className="flex items-center gap-1 text-xs text-emerald-600/60">
                                  <Clock className="size-3" />
                                  休息 {day.rest_seconds}s
                                </span>
                                <Pencil className="size-3.5 text-emerald-400" />
                              </div>
                            </div>
                            {day.exercises.length === 0 ? (
                              <p className="text-xs text-emerald-600/50">休息日</p>
                            ) : (
                              <div className="space-y-1.5">
                                {[...day.exercises]
                                  .sort((a, b) => a.sort_order - b.sort_order)
                                  .slice(0, 3)
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
                                {day.exercises.length > 3 && (
                                  <p className="text-center text-xs text-emerald-500">
                                    +{day.exercises.length - 3} 个动作，点击查看详情
                                  </p>
                                )}
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

              {/* 右栏：饮食计划 */}
              <div className="xl:col-span-1">
                <DietPlanCard dietPlan={dietPlan} />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 训练日详情弹窗 */}
      <DayDetailDialog
        day={selectedDay}
        open={dayDialogOpen}
        onClose={() => setDayDialogOpen(false)}
      />
    </AppLayout>
  );
}