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
import { MetadataEditor, MetadataPreview } from "@/components/metadata-editor";
import { toMetaRows, toMetaDict, type MetaRow } from "@/lib/meta-utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
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
  CheckCircle,
  Search,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

// ============ Types ============

interface ExerciseBrief {
  name: string;
  name_en?: string | null;
  muscle_group?: string | null;
  equipment?: string | null;
  difficulty?: string | null;
  description?: string | null;
}

interface PlanExercise {
  id: string;
  exercise_id: string;
  exercise_name: string | null;
  sets: number;
  reps: number;
  weight_kg: number | null;
  sort_order: number;
  notes?: string | null;
  metadata_?: Record<string, string> | null;
  exercise?: ExerciseBrief | null;
}

interface PlanDay {
  id: string;
  day_of_week: number;
  focus: string | null;
  rest_seconds: number;
  metadata_?: Record<string, string> | null;
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
  metadata_?: Record<string, string> | null;
}

interface DietDay {
  id: string;
  day_of_week: number;
  focus: string | null;
  meals: DietMeal[];
  metadata_?: Record<string, string> | null;
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

const muscleGroupLabels: Record<string, string> = {
  chest: "胸部",
  back: "背部",
  legs: "腿部",
  shoulders: "肩部",
  arms: "手臂",
  core: "核心",
  full_body: "全身",
};

const equipmentLabels: Record<string, string> = {
  barbell: "杠铃",
  dumbbell: "哑铃",
  machine: "器械",
  bodyweight: "自重",
  cable: "绳索",
  kettlebell: "壶铃",
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

// ============ 训练日详情弹窗（可编辑） ============

function DayDetailDialog({
  day,
  open,
  onClose,
  onUpdated,
}: {
  day: PlanDay | null;
  open: boolean;
  onClose: () => void;
  onUpdated: () => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editSets, setEditSets] = useState(3);
  const [editReps, setEditReps] = useState(12);
  const [editWeight, setEditWeight] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editMetadata, setEditMetadata] = useState<MetaRow[]>([]);
  const [saving, setSaving] = useState(false);

  // 训练日信息（名称 / 组间休息 / 自定义项）编辑表单
  const [dayInfoSync, setDayInfoSync] = useState<string | null>(null);
  const [dayFocus, setDayFocus] = useState("");
  const [dayRest, setDayRest] = useState(60);
  const [dayMeta, setDayMeta] = useState<MetaRow[]>([]);
  const [dayInfoSaving, setDayInfoSaving] = useState(false);

  // 添加动作：搜索与结果
  const [exKeyword, setExKeyword] = useState("");
  const [exResults, setExResults] = useState<(ExerciseBrief & { id: string })[]>([]);
  const [exSearching, setExSearching] = useState(false);
  const [addingExId, setAddingExId] = useState<string | null>(null);

  // 渲染期同步：切换训练日时重置表单（避免在 effect 内 setState）
  if (day && day.id !== dayInfoSync) {
    setDayInfoSync(day.id);
    setDayFocus(day.focus ?? "");
    setDayRest(day.rest_seconds);
    setDayMeta(toMetaRows(day.metadata_));
    setEditingId(null);
    setExKeyword("");
    setExResults([]);
  }

  if (!day) return null;

  const startEdit = (ex: PlanExercise) => {
    setEditingId(ex.id);
    setEditSets(ex.sets);
    setEditReps(ex.reps);
    setEditWeight(ex.weight_kg?.toString() ?? "");
    setEditNotes(ex.notes ?? "");
    setEditMetadata(toMetaRows(ex.metadata_));
  };

  const saveEdit = async (exId: string) => {
    setSaving(true);
    try {
      await api.put(`/plans/exercises/${exId}`, {
        sets: editSets,
        reps: editReps,
        weight_kg: editWeight ? parseFloat(editWeight) : null,
        notes: editNotes.trim() ? editNotes.trim() : null,
        metadata_: toMetaDict(editMetadata),
      });
      setEditingId(null);
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const deleteExercise = async (exId: string) => {
    if (!confirm("确定删除该动作？")) return;
    try {
      await api.delete(`/plans/exercises/${exId}`);
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const saveDayInfo = async () => {
    setDayInfoSaving(true);
    try {
      await api.put(`/plans/days/${day.id}`, {
        focus: dayFocus.trim() || null,
        rest_seconds: dayRest,
        metadata_: toMetaDict(dayMeta),
      });
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setDayInfoSaving(false);
    }
  };

  const searchExercises = async () => {
    setExSearching(true);
    try {
      const kw = exKeyword.trim();
      const list = await api.get<(ExerciseBrief & { id: string })[]>(
        `/exercises?limit=20${kw ? `&keyword=${encodeURIComponent(kw)}` : ""}`
      );
      setExResults(list || []);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setExSearching(false);
    }
  };

  const addExerciseToDay = async (ex: ExerciseBrief & { id: string }) => {
    setAddingExId(ex.id);
    try {
      await api.post(`/plans/days/${day.id}/exercises`, {
        exercise_id: ex.id,
        sets: 3,
        reps: 12,
        weight_kg: null,
        sort_order: day.exercises.length,
        notes: null,
      });
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setAddingExId(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-950">
            <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
              {dayNames[day.day_of_week - 1]}
            </span>
            {day.focus || "综合训练"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          {/* 训练日信息编辑 */}
          <div className="space-y-2 rounded-lg border border-emerald-100 bg-emerald-50/40 p-3">
            <div className="flex items-center gap-2">
              <span className="w-16 shrink-0 text-xs font-medium text-emerald-700">训练重点</span>
              <Input
                value={dayFocus}
                onChange={(e) => setDayFocus(e.target.value)}
                placeholder="如 胸部 + 三头"
                className="h-8 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="w-16 shrink-0 text-xs font-medium text-emerald-700">组间休息</span>
              <Input
                type="number"
                min={0}
                value={dayRest}
                onChange={(e) => setDayRest(parseInt(e.target.value) || 0)}
                className="h-8 w-24 text-sm"
              />
              <span className="text-xs text-emerald-600">秒</span>
            </div>
            <div>
              <p className="mb-1 text-xs font-medium text-emerald-700">自定义项（可选）</p>
              <MetadataEditor value={dayMeta} onChange={setDayMeta} />
            </div>
            <div className="flex justify-end">
              <Button size="sm" className="h-7 text-xs" onClick={saveDayInfo} disabled={dayInfoSaving}>
                {dayInfoSaving ? "保存中..." : "保存训练日信息"}
              </Button>
            </div>
          </div>

          {/* 添加动作 */}
          <div className="space-y-2">
            <p className="text-xs font-medium text-emerald-700">添加动作</p>
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-emerald-400" />
                <Input
                  value={exKeyword}
                  onChange={(e) => setExKeyword(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      searchExercises();
                    }
                  }}
                  placeholder="搜索动作名称（如 卧推 / 深蹲）"
                  className="h-8 pl-7 text-sm"
                />
              </div>
              <Button size="sm" variant="outline" className="h-8 text-xs" onClick={searchExercises} disabled={exSearching}>
                {exSearching ? "搜索中..." : "搜索"}
              </Button>
            </div>
            {exResults.length > 0 && (
              <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border border-emerald-100 p-1">
                {exResults.map((ex) => (
                  <button
                    key={ex.id}
                    type="button"
                    disabled={addingExId === ex.id}
                    onClick={() => addExerciseToDay(ex)}
                    className="flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm hover:bg-emerald-50 disabled:opacity-50"
                  >
                    <span className="flex min-w-0 items-center gap-1.5">
                      <span className="truncate font-medium text-emerald-900">{ex.name}</span>
                      {ex.muscle_group && (
                        <Badge variant="outline" className="h-4 shrink-0 border-emerald-200 px-1 text-[9px] text-emerald-600">
                          {muscleGroupLabels[ex.muscle_group] ?? ex.muscle_group}
                        </Badge>
                      )}
                    </span>
                    <Plus className="size-3.5 shrink-0 text-emerald-500" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* 当日动作列表 */}
          <p className="text-xs font-medium text-emerald-700">
            当日动作（{day.exercises.length}）
          </p>
          {day.exercises.length === 0 ? (
            <p className="py-4 text-center text-sm text-emerald-600/50">暂无动作，在上方搜索并添加</p>
          ) : (
            <div className="space-y-2">
              {[...day.exercises]
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((ex, idx) => (
                  <div
                    key={ex.id}
                    className="rounded-lg border border-emerald-100 bg-emerald-50/50 px-4 py-3"
                  >
                    {editingId === ex.id ? (
                      <div className="space-y-2">
                        <p className="font-medium text-emerald-900">{ex.exercise_name ?? "未知动作"}</p>
                        <div className="flex items-center gap-2">
                          <div className="flex items-center gap-1">
                            <Input
                              type="number"
                              min={1}
                              max={20}
                              value={editSets}
                              onChange={(e) => setEditSets(parseInt(e.target.value) || 1)}
                              className="w-16 h-8 text-sm"
                            />
                            <span className="text-xs text-emerald-600">组</span>
                          </div>
                          <span className="text-emerald-400">×</span>
                          <div className="flex items-center gap-1">
                            <Input
                              type="number"
                              min={1}
                              max={100}
                              value={editReps}
                              onChange={(e) => setEditReps(parseInt(e.target.value) || 1)}
                              className="w-16 h-8 text-sm"
                            />
                            <span className="text-xs text-emerald-600">次</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Input
                              type="number"
                              min={0}
                              step={0.5}
                              placeholder="重量"
                              value={editWeight}
                              onChange={(e) => setEditWeight(e.target.value)}
                              className="w-20 h-8 text-sm"
                            />
                            <span className="text-xs text-emerald-600">kg</span>
                          </div>
                        </div>
                        <Textarea
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          placeholder="动作要点 / 备注（如：腰背挺直，下放吸气）"
                          className="min-h-16 resize-none text-sm"
                        />
                        <MetadataEditor
                          value={editMetadata}
                          onChange={setEditMetadata}
                        />
                        <div className="flex gap-2">
                          <Button size="sm" className="h-7 text-xs" onClick={() => saveEdit(ex.id)} disabled={saving}>
                            {saving ? "保存中..." : "保存"}
                          </Button>
                          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditingId(null)}>
                            取消
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-emerald-200 text-xs font-bold text-emerald-700">
                          {idx + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <p className="font-medium text-emerald-900">
                              {ex.exercise?.name ?? ex.exercise_name ?? "未知动作"}
                            </p>
                            {ex.exercise?.muscle_group && (
                              <Badge
                                variant="outline"
                                className="h-5 border-emerald-200 px-1.5 text-[10px] text-emerald-600"
                              >
                                {muscleGroupLabels[ex.exercise.muscle_group] ?? ex.exercise.muscle_group}
                              </Badge>
                            )}
                            {ex.exercise?.equipment && (
                              <Badge
                                variant="outline"
                                className="h-5 border-sky-200 bg-sky-50 px-1.5 text-[10px] text-sky-600"
                              >
                                {equipmentLabels[ex.exercise.equipment] ?? ex.exercise.equipment}
                              </Badge>
                            )}
                          </div>
                          <p className="mt-0.5 text-xs text-emerald-600/70">
                            <span className="font-medium text-emerald-700">
                              {ex.sets} 组 × {ex.reps} 次
                            </span>
                            {ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}
                          </p>
                          {ex.exercise?.description && (
                            <p className="mt-1 line-clamp-2 text-xs text-emerald-600/60">
                              {ex.exercise.description}
                            </p>
                          )}
                          {ex.notes && (
                            <p className="mt-1 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
                              <span className="font-medium">要点：</span>
                              {ex.notes}
                            </p>
                          )}
                          <div className="mt-1">
                            <MetadataPreview value={ex.metadata_} />
                          </div>
                        </div>
                        <div className="flex shrink-0 flex-col gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7 text-emerald-400 hover:text-emerald-600"
                            onClick={() => startEdit(ex)}
                          >
                            <Pencil className="size-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7 text-red-300 hover:text-red-600"
                            onClick={() => deleteExercise(ex.id)}
                          >
                            <Trash2 className="size-3.5" />
                          </Button>
                        </div>
                      </div>
                    )}
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

// ============ 饮食计划组件（可编辑） ============

function DietPlanCard({
  dietPlan,
  onUpdated,
}: {
  dietPlan: DietPlanDetail | null;
  onUpdated: () => void;
}) {
  const [selectedDay, setSelectedDay] = useState<number>(1);
  const [editingMealId, setEditingMealId] = useState<string | null>(null);
  const [editFood, setEditFood] = useState("");
  const [editCalories, setEditCalories] = useState("");
  const [editProtein, setEditProtein] = useState("");
  const [editCarbs, setEditCarbs] = useState("");
  const [editFat, setEditFat] = useState("");
  const [editPortion, setEditPortion] = useState("");
  const [editMealMetadata, setEditMealMetadata] = useState<MetaRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [editingDayId, setEditingDayId] = useState<string | null>(null);
  const [editDayFocus, setEditDayFocus] = useState("");
  const [editDayMetadata, setEditDayMetadata] = useState<MetaRow[]>([]);

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

  const startEditMeal = (meal: DietMeal) => {
    setEditingMealId(meal.id);
    setEditFood(meal.food_name);
    setEditCalories(meal.calories?.toString() ?? "");
    setEditProtein(meal.protein_g?.toString() ?? "");
    setEditCarbs(meal.carbs_g?.toString() ?? "");
    setEditFat(meal.fat_g?.toString() ?? "");
    setEditPortion(meal.portion ?? "");
    setEditMealMetadata(toMetaRows(meal.metadata_));
  };

  const saveMealEdit = async (mealId: string) => {
    setSaving(true);
    try {
      await api.put(`/diet-plans/meals/${mealId}`, {
        food_name: editFood,
        calories: editCalories ? parseInt(editCalories) : null,
        protein_g: editProtein ? parseFloat(editProtein) : null,
        carbs_g: editCarbs ? parseFloat(editCarbs) : null,
        fat_g: editFat ? parseFloat(editFat) : null,
        portion: editPortion || null,
        metadata_: toMetaDict(editMealMetadata),
      });
      setEditingMealId(null);
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const deleteMeal = async (mealId: string) => {
    if (!confirm("确定删除该餐食？")) return;
    try {
      await api.delete(`/diet-plans/meals/${mealId}`);
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const startEditDay = (day: DietDay) => {
    setEditingDayId(day.id);
    setEditDayFocus(day.focus ?? "");
    setEditDayMetadata(toMetaRows(day.metadata_));
  };

  const saveDayEdit = async (dayId: string) => {
    setSaving(true);
    try {
      await api.put(`/diet-plans/days/${dayId}`, {
        focus: editDayFocus.trim() || null,
        metadata_: toMetaDict(editDayMetadata),
      });
      setEditingDayId(null);
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

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
            {editingDayId === currentDay.id ? (
              <div className="space-y-2 rounded-lg border border-orange-200 bg-orange-50/50 p-2">
                <Input
                  value={editDayFocus}
                  onChange={(e) => setEditDayFocus(e.target.value)}
                  placeholder="今日饮食重点"
                  className="h-8 text-sm"
                />
                <MetadataEditor value={editDayMetadata} onChange={setEditDayMetadata} />
                <div className="flex gap-2">
                  <Button size="sm" className="h-7 text-xs" onClick={() => saveDayEdit(currentDay.id)} disabled={saving}>
                    {saving ? "保存中..." : "保存"}
                  </Button>
                  <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditingDayId(null)}>
                    取消
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  {currentDay.focus ? (
                    <p className="text-xs font-medium text-orange-600/70">📋 {currentDay.focus}</p>
                  ) : (
                    <span />
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-6 text-orange-300 hover:text-orange-600"
                    onClick={() => startEditDay(currentDay)}
                  >
                    <Pencil className="size-3" />
                  </Button>
                </div>
                <MetadataPreview value={currentDay.metadata_} />
              </div>
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
                  {editingMealId === meal.id ? (
                    <div className="space-y-2">
                      <Input
                        value={editFood}
                        onChange={(e) => setEditFood(e.target.value)}
                        placeholder="食物名称"
                        className="h-8 text-sm"
                      />
                      <div className="grid grid-cols-2 gap-2">
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            value={editCalories}
                            onChange={(e) => setEditCalories(e.target.value)}
                            placeholder="卡路里"
                            className="h-7 text-xs"
                          />
                          <span className="text-[10px] text-orange-500">kcal</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Input
                            value={editPortion}
                            onChange={(e) => setEditPortion(e.target.value)}
                            placeholder="份量"
                            className="h-7 text-xs"
                          />
                        </div>
                      </div>
                      <div className="grid grid-cols-3 gap-2">
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            step={0.1}
                            value={editProtein}
                            onChange={(e) => setEditProtein(e.target.value)}
                            placeholder="蛋白质"
                            className="h-7 text-xs"
                          />
                          <span className="text-[10px] text-orange-500">g</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            step={0.1}
                            value={editCarbs}
                            onChange={(e) => setEditCarbs(e.target.value)}
                            placeholder="碳水"
                            className="h-7 text-xs"
                          />
                          <span className="text-[10px] text-orange-500">g</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            step={0.1}
                            value={editFat}
                            onChange={(e) => setEditFat(e.target.value)}
                            placeholder="脂肪"
                            className="h-7 text-xs"
                          />
                          <span className="text-[10px] text-orange-500">g</span>
                        </div>
                      </div>
                      <MetadataEditor value={editMealMetadata} onChange={setEditMealMetadata} />
                      <div className="flex gap-2">
                        <Button size="sm" className="h-7 text-xs" onClick={() => saveMealEdit(meal.id)} disabled={saving}>
                          {saving ? "保存中..." : "保存"}
                        </Button>
                        <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditingMealId(null)}>
                          取消
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div className="mb-2 flex items-center justify-between">
                        <span
                          className={cn(
                            "rounded-md px-2 py-0.5 text-xs font-medium",
                            mealTypeColors[meal.meal_type] ?? "bg-gray-100 text-gray-600"
                          )}
                        >
                          {mealTypeLabels[meal.meal_type] ?? meal.meal_type}
                        </span>
                        <div className="flex items-center gap-1">
                          {meal.calories && (
                            <span className="text-xs font-medium text-orange-600">{meal.calories} kcal</span>
                          )}
                          <Button variant="ghost" size="icon" className="size-6 text-orange-300 hover:text-orange-600" onClick={() => startEditMeal(meal)}>
                            <Pencil className="size-3" />
                          </Button>
                          <Button variant="ghost" size="icon" className="size-6 text-red-300 hover:text-red-600" onClick={() => deleteMeal(meal.id)}>
                            <Trash2 className="size-3" />
                          </Button>
                        </div>
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
                      <div className="mt-1">
                        <MetadataPreview value={meal.metadata_} />
                      </div>
                    </>
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
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [planToDeleteId, setPlanToDeleteId] = useState<string | null>(null);
  const [checkinLoading, setCheckinLoading] = useState<string | null>(null);

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

  const requestDelete = (id: string) => {
    setPlanToDeleteId(id);
    setDeleteDialogOpen(true);
  };

  const executeDelete = async () => {
    if (!planToDeleteId) return;
    try {
      await api.delete(`/plans/${planToDeleteId}`);
      setPlans((prev) => prev.filter((p) => p.id !== planToDeleteId));
      if (selectedId === planToDeleteId) {
        setSelectedId(null);
        setSelectedPlan(null);
      }
      if (activePlan?.id === planToDeleteId) setActivePlan(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDeleteDialogOpen(false);
      setPlanToDeleteId(null);
    }
  };

  const openDayDetail = (day: PlanDay) => {
    setSelectedDay(day);
    setDayDialogOpen(true);
  };

  const deleteTrainingDay = async (dayId: string) => {
    if (!confirm("确定删除该训练日？")) return;
    try {
      await api.delete(`/plans/days/${dayId}`);
      const planId = selectedId ?? activePlan?.id;
      if (planId) {
        const detail = await api.get<PlanDetail>(`/plans/${planId}`);
        setSelectedPlan(detail);
        if (activePlan?.id === planId) setActivePlan(detail);
      }
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const addTrainingDay = async () => {
    const planId = selectedId ?? activePlan?.id;
    if (!planId) return;
    const displayDays = selectedPlan?.days ?? activePlan?.days ?? [];
    const usedDays = new Set(displayDays.map((d) => d.day_of_week));
    const nextDay = [1, 2, 3, 4, 5, 6, 7].find((d) => !usedDays.has(d));
    if (!nextDay) {
      alert("已存在周一到周日的训练日，无法再添加");
      return;
    }
    try {
      await api.post(`/plans/${planId}/days`, {
        day_of_week: nextDay,
        focus: `训练日 ${dayNames[nextDay - 1]}`,
        rest_seconds: 60,
        exercises: [],
      });
      const detail = await api.get<PlanDetail>(`/plans/${planId}`);
      setSelectedPlan(detail);
      if (activePlan?.id === planId) setActivePlan(detail);
    } catch (e) {
      alert((e as Error).message);
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
      alert((e as Error).message);
    } finally {
      setCheckinLoading(null);
    }
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
            <div className="space-y-6">
              {/* 顶部：打卡日历 + 全部计划 */}
              <div className="grid gap-6 lg:grid-cols-3">
                <div className="lg:col-span-1">
                  <CheckinCalendar checkinDates={checkinDates} streak={streak} />
                </div>
                <div className="lg:col-span-2">

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
              </div>

              {/* 底部：训练计划 + 饮食计划 两列 */}
              <div className="grid gap-6 lg:grid-cols-2">
                {/* 训练计划详情 */}
                <div>
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
                          onClick={() => requestDelete(displayPlan.id)}
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
                            className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-4 transition-all hover:border-emerald-300 hover:shadow-sm"
                          >
                              <>
                                <div className="mb-2 flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
                                      {dayNames[day.day_of_week - 1]}
                                    </span>
                                    <span className="font-medium text-emerald-900">
                                      {day.focus || "综合训练"}
                                    </span>
                                  </div>
                                  <div className="flex items-center gap-0.5">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      title="编辑"
                                      className="size-7 text-emerald-400 hover:text-emerald-600"
                                      onClick={() => openDayDetail(day)}
                                    >
                                      <Pencil className="size-3.5" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      title="打卡"
                                      className="size-7 text-emerald-400 hover:text-orange-600"
                                      onClick={() => checkinDay(day)}
                                      disabled={checkinLoading === day.id}
                                    >
                                      <CheckCircle className="size-3.5" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      title="删除"
                                      className="size-7 text-emerald-400 hover:text-red-600"
                                      onClick={() => deleteTrainingDay(day.id)}
                                    >
                                      <Trash2 className="size-3.5" />
                                    </Button>
                                  </div>
                                </div>
                                <div className="mb-2 flex items-center gap-1 text-xs text-emerald-600/60">
                                  <Clock className="size-3" />
                                  休息 {day.rest_seconds}s
                                </div>
                                <div className="mb-2">
                                  <MetadataPreview value={day.metadata_} />
                                </div>
                                <div onClick={() => openDayDetail(day)} className="cursor-pointer">
                                  {day.exercises.length === 0 ? (
                                    <p className="text-xs text-emerald-600/50">暂无动作，点击编辑添加</p>
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
                              </>
                          </div>
                        ))}
                      <Button
                        variant="outline"
                        className="w-full border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                        onClick={addTrainingDay}
                      >
                        <Plus className="mr-1 size-4" />
                        添加训练日
                      </Button>
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

                {/* 饮食计划 */}
                <div>
                <DietPlanCard
                  dietPlan={dietPlan}
                  onUpdated={() => {
                    api.get<DietPlanDetail | null>("/diet-plans/active").then((diet) => {
                      setDietPlan(diet);
                    });
                  }}
                />
                </div>
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
        onUpdated={() => {
          // 重新加载当前计划详情
          const planId = selectedId ?? activePlan?.id;
          if (planId) {
            api.get<PlanDetail>(`/plans/${planId}`).then((detail) => {
              setSelectedPlan(detail);
              // 更新 selectedDay 以反映最新数据
              const updatedDay = detail.days.find((d) => d.id === selectedDay?.id);
              if (updatedDay) setSelectedDay(updatedDay);
            });
          }
        }}
      />

      {/* 删除训练计划确认弹窗 */}
      <Dialog
        open={deleteDialogOpen}
        onOpenChange={(open) => {
          setDeleteDialogOpen(open);
          if (!open) setPlanToDeleteId(null);
        }}
      >
        <DialogContent className="max-w-sm border-emerald-100 bg-white/95 backdrop-blur">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-emerald-950">
              <Trash2 className="size-4 text-red-500" />
              删除训练计划
            </DialogTitle>
          </DialogHeader>
          <div className="py-2">
            <p className="text-sm text-emerald-700/80">
              确定删除训练计划「{plans.find((p) => p.id === planToDeleteId)?.name ?? ""}」？删除后将无法恢复。
            </p>
          </div>
          <DialogFooter className="gap-2">
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
            >
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={executeDelete}
              className="bg-red-500 text-white hover:bg-red-600"
            >
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}