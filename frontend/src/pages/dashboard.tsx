import { useState, useMemo, useEffect, useCallback, useRef, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  AreaChart,
  Area,
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AppLayout } from "@/components/app-layout";
import { TodayOverviewBar } from "@/components/today-overview-bar";
import {
  Flame,
  Dumbbell,
  Target,
  TrendingUp,
  Zap,
  Loader2,
  Clock,
  Smile,
  StickyNote,
  Apple,
  Utensils,
  BarChart3,
  Scale,
  Pencil,
  Check,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

// ============ 数据类型 ============

interface DietMealRecord {
  id: string;
  meal_type: string;
  food_name: string;
  calories: number;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
}

interface UserSettings {
  calorie_goal: number;
  protein_goal_g: number;
  carbs_goal_g: number;
  fat_goal_g: number;
}

interface OverviewStats {
  total_workouts: number;
  total_duration_min: number;
  current_streak: number;
  longest_streak: number;
}

interface WeeklyStats {
  week_start: string;
  week_end: string;
  total_workouts: number;
  total_duration_min: number;
  total_sets: number;
  daily_breakdown: {
    date: string;
    completed: boolean;
    duration_min: number;
  }[];
}

interface BodyStats {
  current_weight_kg: number | null;
  height_cm: number | null;
  goal: string | null;
}

interface CheckinExercise {
  id: string;
  exercise_name: string | null;
  sets_done: number | null;
  reps_done: number | null;
  weight_kg: number | null;
}

interface CheckinItem {
  id: string;
  date: string;
  duration_min: number | null;
  calories_burned: number | null;
  mood: number | null;
  note: string | null;
  exercises: CheckinExercise[];
}

const dayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const moodEmojis = ["😫", "😕", "😐", "🙂", "🤩"];

// ============ 大方块统一外壳 ============

function DashCard({
  icon,
  title,
  action,
  children,
  className,
}: {
  icon?: ReactNode;
  title: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <Card
      className={cn(
        "flex flex-col overflow-hidden border-emerald-100 bg-white/80 shadow-sm backdrop-blur transition-shadow duration-200 hover:shadow-md",
        className,
      )}
    >
      <CardHeader className="p-4 pb-2 sm:p-6 sm:pb-3">
        <CardTitle className="flex min-w-0 items-center gap-2 text-sm font-semibold text-emerald-950 sm:text-base">
          {icon}
          <span className="min-w-0 flex-1 truncate">{title}</span>
          {action}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-4 pt-1 sm:p-6 sm:pt-1">{children}</CardContent>
    </Card>
  );
}

// ============ 今日训练卡片 ============

function TodayTraining({ checkin }: { checkin: CheckinItem | null }) {
  return (
    <DashCard icon={<Dumbbell className="size-4 text-emerald-500" />} title="今日训练">
      {checkin ? (
        <div className="space-y-2 sm:space-y-3">
          {checkin.duration_min != null && (
            <div className="flex flex-col gap-1 rounded-lg bg-emerald-50/60 px-3 py-2 sm:flex-row sm:items-center sm:justify-between sm:px-4 sm:py-3">
              <span className="text-xs text-emerald-700 sm:text-sm">训练时长</span>
              <span className="flex items-center gap-1.5 text-base font-bold text-emerald-950 sm:text-lg">
                <Clock className="size-4 text-emerald-500" />
                {checkin.duration_min} 分钟
              </span>
            </div>
          )}
          {checkin.mood && (
            <div className="flex flex-col gap-1 rounded-lg bg-emerald-50/60 px-3 py-2 sm:flex-row sm:items-center sm:justify-between sm:px-4 sm:py-3">
              <span className="text-xs text-emerald-700 sm:text-sm">心情评分</span>
              <span className="flex items-center gap-1.5 text-base font-bold text-emerald-950 sm:text-lg">
                <Smile className="size-4 text-emerald-500" />
                {moodEmojis[checkin.mood - 1]}
              </span>
            </div>
          )}
          {checkin.exercises.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs font-medium text-emerald-600/60">训练动作</p>
              {checkin.exercises.map((ex) => (
                <div
                  key={ex.id}
                  className="rounded-lg bg-emerald-50/40 px-2.5 py-1.5 sm:flex sm:items-center sm:justify-between sm:gap-2 sm:px-3 sm:py-2"
                >
                  <span className="block truncate text-xs font-medium text-emerald-900 sm:text-sm">
                    {ex.exercise_name ?? "未知动作"}
                  </span>
                  <span className="shrink-0 text-[11px] tabular-nums text-emerald-600/70 sm:text-xs">
                    {ex.sets_done ?? "-"} 组 × {ex.reps_done ?? "-"} 次
                    {ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
          {checkin.note && (
            <div className="flex items-start gap-2 rounded-lg bg-emerald-50/40 px-2.5 py-2 text-xs text-emerald-700 sm:px-3 sm:text-sm">
              <StickyNote className="mt-0.5 size-3.5 shrink-0 text-emerald-400" />
              <span className="line-clamp-3">{checkin.note}</span>
            </div>
          )}
        </div>
      ) : (
        <div className="flex h-full flex-col items-center justify-center gap-2.5 py-6 text-center sm:gap-3 sm:py-8">
          <Dumbbell className="size-7 text-emerald-200 sm:size-8" />
          <p className="text-xs text-emerald-600/60 sm:text-sm">今天还没有训练记录</p>
          <p className="text-[11px] text-emerald-500/50 sm:text-xs">去 AI 教练那里获取今日训练建议吧</p>
        </div>
      )}
    </DashCard>
  );
}

// ============ 饮食卡路里卡片 ============

type MacroKey = "protein_goal_g" | "carbs_goal_g" | "fat_goal_g";

function NutritionCard() {
  const [totals, setTotals] = useState<{
    calories: number;
    protein: number;
    carbs: number;
    fat: number;
  } | null>(null);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [editingKey, setEditingKey] = useState<MacroKey | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const editInputRef = useRef<HTMLInputElement>(null);

  const loadData = useCallback(() => {
    const today = format(new Date(), "yyyy-MM-dd");
    Promise.all([
      api.get<UserSettings>("/users/settings").catch(() => null),
      api
        .get<{ items: DietMealRecord[] }>(
          `/diet-meals?start=${today}&end=${today}&size=100`,
        )
        .catch(() => null),
    ]).then(([s, mealRes]) => {
      if (s) setSettings(s);
      const items = mealRes?.items ?? [];
      setTotals(
        items.reduce(
          (acc, m) => ({
            calories: acc.calories + (m.calories || 0),
            protein: acc.protein + (m.protein_g || 0),
            carbs: acc.carbs + (m.carbs_g || 0),
            fat: acc.fat + (m.fat_g || 0),
          }),
          { calories: 0, protein: 0, carbs: 0, fat: 0 },
        ),
      );
    });
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (editingKey && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingKey]);

  const startEdit = (key: MacroKey, currentVal: number) => {
    setEditingKey(key);
    setEditValue(String(currentVal));
  };

  const cancelEdit = () => {
    setEditingKey(null);
    setEditValue("");
  };

  const saveEdit = async (key: MacroKey) => {
    const num = parseFloat(editValue);
    if (isNaN(num) || num < 0) {
      cancelEdit();
      return;
    }
    setSaving(true);
    try {
      const updated = await api.put<UserSettings>("/users/settings", { [key]: num });
      if (updated) setSettings(updated);
    } catch {
      // silent
    } finally {
      setSaving(false);
      setEditingKey(null);
    }
  };

  const targetCalories = settings?.calorie_goal ?? 2000;
  const consumedCalories = totals?.calories ?? 0;
  const percent =
    targetCalories > 0
      ? Math.min(100, Math.round((consumedCalories / targetCalories) * 100))
      : 0;

  const macros: {
    label: string;
    value: number;
    target: number;
    color: string;
    key: MacroKey;
  }[] = [
    {
      label: "蛋白质",
      value: totals?.protein ?? 0,
      target: settings?.protein_goal_g ?? 0,
      color: "bg-emerald-500",
      key: "protein_goal_g",
    },
    {
      label: "碳水",
      value: totals?.carbs ?? 0,
      target: settings?.carbs_goal_g ?? 0,
      color: "bg-amber-500",
      key: "carbs_goal_g",
    },
    {
      label: "脂肪",
      value: totals?.fat ?? 0,
      target: settings?.fat_goal_g ?? 0,
      color: "bg-sky-500",
      key: "fat_goal_g",
    },
  ];

  return (
    <DashCard icon={<Apple className="size-4 text-emerald-500" />} title="饮食记录">
      <div className="relative mx-auto size-28 sm:size-32">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            innerRadius="75%"
            outerRadius="100%"
            data={[{ name: "calories", value: percent, fill: "#f59e0b" }]}
            startAngle={90}
            endAngle={-270}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar background={{ fill: "#fef3c7" }} cornerRadius={10} dataKey="value" />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-xl font-bold tabular-nums text-emerald-950 sm:text-2xl">
            {consumedCalories}
          </span>
          <span className="text-[10px] text-emerald-600/60 sm:text-xs">/ {targetCalories} kcal</span>
        </div>
      </div>
      <div className="mt-3 space-y-2.5 sm:mt-4">
        {macros.map((m) => {
          const pct =
            m.target > 0 ? Math.min(100, Math.round((m.value / m.target) * 100)) : 0;
          const isEditing = editingKey === m.key;
          return (
            <div key={m.key}>
              <div className="mb-1 flex items-center justify-between gap-2 text-xs">
                <span className="font-medium text-emerald-800">{m.label}</span>
                {isEditing ? (
                  <span className="flex items-center gap-1">
                    <span className="tabular-nums text-emerald-600/70">
                      {Math.round(m.value * 10) / 10} /
                    </span>
                    <input
                      ref={editInputRef}
                      type="number"
                      min={0}
                      step={1}
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          e.preventDefault();
                          saveEdit(m.key);
                        } else if (e.key === "Escape") {
                          cancelEdit();
                        }
                      }}
                      disabled={saving}
                      className="h-5 w-14 rounded border border-emerald-200 bg-white px-1 text-right text-xs tabular-nums text-emerald-800 outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-200"
                    />
                    <span className="text-emerald-600/70">g</span>
                    <button
                      type="button"
                      onClick={() => saveEdit(m.key)}
                      disabled={saving}
                      className="flex size-4 items-center justify-center rounded text-emerald-600 transition-colors hover:bg-emerald-100"
                      title="保存"
                    >
                      <Check className="size-3" />
                    </button>
                    <button
                      type="button"
                      onClick={cancelEdit}
                      className="flex size-4 items-center justify-center rounded text-emerald-400 transition-colors hover:bg-red-50 hover:text-red-500"
                      title="取消"
                    >
                      <X className="size-3" />
                    </button>
                  </span>
                ) : (
                  <button
                    type="button"
                    onClick={() => startEdit(m.key, m.target)}
                    className="group/target flex items-center gap-0.5 rounded px-0.5 transition-colors hover:bg-emerald-50"
                    title="点击编辑目标值"
                  >
                    <span className="tabular-nums text-emerald-600/70">
                      {Math.round(m.value * 10) / 10} / {m.target} g
                    </span>
                    <Pencil className="size-2.5 text-emerald-300 opacity-0 transition-opacity group-hover/target:opacity-100" />
                  </button>
                )}
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-emerald-100/70">
                <div
                  className={cn("h-full rounded-full transition-all", m.color)}
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <Link
        to="/plans"
        className="mt-3 flex items-center justify-center gap-1 rounded-lg bg-orange-50 py-2 text-xs font-medium text-orange-700 transition-colors hover:bg-orange-100 sm:mt-4"
      >
        <Utensils className="size-3.5" />
        去饮食记录
      </Link>
    </DashCard>
  );
}

// ============ 本周目标卡片 ============

function WeeklyGoalCard({
  weekly,
  goalPercent,
  weeklyTotal,
  avgDuration,
}: {
  weekly: WeeklyStats | null;
  goalPercent: number;
  weeklyTotal: number;
  avgDuration: number;
}) {
  return (
    <DashCard icon={<Target className="size-4 text-emerald-500" />} title="本周目标">
      <div className="relative mx-auto size-28 sm:size-36">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            innerRadius="75%"
            outerRadius="100%"
            data={[{ name: "goal", value: goalPercent, fill: "#10b981" }]}
            startAngle={90}
            endAngle={-270}
          >
            <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
            <RadialBar background={{ fill: "#d1fae5" }} cornerRadius={10} dataKey="value" />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-2xl font-bold tabular-nums text-emerald-950 sm:text-3xl">
            {goalPercent}%
          </span>
          <span className="text-[10px] text-emerald-600/60 sm:text-xs">
            {weeklyTotal}/300 分钟
          </span>
        </div>
      </div>
      <div className="mt-3 space-y-2 sm:mt-4">
        <div className="flex justify-between text-xs sm:text-sm">
          <span className="text-emerald-600/60">训练次数</span>
          <span className="font-medium text-emerald-950">{weekly?.total_workouts ?? 0} 次</span>
        </div>
        <div className="flex justify-between text-xs sm:text-sm">
          <span className="text-emerald-600/60">完成组数</span>
          <span className="font-medium text-emerald-950">{weekly?.total_sets ?? 0} 组</span>
        </div>
        <div className="flex justify-between text-xs sm:text-sm">
          <span className="text-emerald-600/60">平均时长</span>
          <span className="font-medium text-emerald-950">{avgDuration} 分钟/次</span>
        </div>
      </div>
    </DashCard>
  );
}

// ============ 本周训练量图表卡片 ============

function WeeklyVolumeCard({
  data,
  total,
}: {
  data: { day: string; minutes: number }[];
  total: number;
}) {
  return (
    <DashCard
      icon={<BarChart3 className="size-4 text-emerald-500" />}
      title="本周训练量"
      action={
        <span className="hidden shrink-0 text-xs font-normal text-emerald-600/60 sm:inline">
          总计 {total} 分钟
        </span>
      }
    >
      <div className="h-32 sm:h-44">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 4, left: 0, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#d1fae5" vertical={false} />
            <XAxis
              dataKey="day"
              tick={{ fill: "#6ee7b7", fontSize: 10 }}
              axisLine={false}
              tickLine={false}
            />
            <YAxis width={28} tick={{ fill: "#6ee7b7", fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                backgroundColor: "#ffffff",
                border: "1px solid #d1fae5",
                borderRadius: "12px",
                fontSize: "12px",
                boxShadow: "0 4px 12px rgba(16,185,129,0.1)",
              }}
              labelStyle={{ color: "#065f46" }}
              cursor={{ fill: "#ecfdf5", opacity: 0.8 }}
            />
            <Bar dataKey="minutes" name="时长 (分钟)" fill="#10b981" radius={[6, 6, 0, 0]} maxBarSize={32} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </DashCard>
  );
}

// ============ 心情趋势图表卡片 ============

function MoodTrendCard({ checkins }: { checkins: CheckinItem[] }) {
  const moodData = useMemo(
    () =>
      checkins
        .filter((c) => c.mood != null)
        .slice(0, 10)
        .reverse()
        .map((c) => ({
          label: format(parseISO(c.date), "M/d"),
          mood: c.mood as number,
        })),
    [checkins],
  );

  return (
    <DashCard
      icon={<Smile className="size-4 text-amber-500" />}
      title="心情趋势"
      action={
        moodData.length > 0 ? (
          <span className="hidden shrink-0 text-xs font-normal text-emerald-600/60 sm:inline">
            最近 {moodData.length} 次打卡
          </span>
        ) : undefined
      }
    >
      {moodData.length === 0 ? (
        <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 py-4 text-center sm:min-h-44">
          <span className="text-3xl">😐</span>
          <p className="text-xs text-emerald-600/60 sm:text-sm">还没有心情记录</p>
          <p className="text-[11px] text-emerald-500/50 sm:text-xs">训练打卡时记录一下当天心情吧</p>
        </div>
      ) : (
        <div className="h-32 sm:h-44">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={moodData} margin={{ top: 14, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="moodGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.32} />
                  <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#d1fae5" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fill: "#6ee7b7", fontSize: 10 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[1, 5]}
                ticks={[1, 2, 3, 4, 5]}
                tickFormatter={(v: number) => moodEmojis[v - 1] ?? ""}
                tick={{ fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={40}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#ffffff",
                  border: "1px solid #d1fae5",
                  borderRadius: "12px",
                  fontSize: "12px",
                  boxShadow: "0 4px 12px rgba(16,185,129,0.1)",
                }}
                labelStyle={{ color: "#065f46" }}
                formatter={(value) => [`${moodEmojis[Number(value) - 1] ?? ""} ${value}/5`, "心情"]}
              />
              <Area
                type="monotone"
                dataKey="mood"
                stroke="#f59e0b"
                strokeWidth={2}
                fill="url(#moodGradient)"
                activeDot={{ r: 4, fill: "#f59e0b" }}
                dot={(props) => {
                  const { cx, cy, payload, index } = props as {
                    cx?: number;
                    cy?: number;
                    payload?: { mood: number };
                    index?: number;
                  };
                  if (cx == null || cy == null || !payload) return <g key={`md-${index}`} />;
                  return (
                    <text
                      key={`md-${index}`}
                      x={cx}
                      y={cy - 8}
                      textAnchor="middle"
                      fontSize={12}
                    >
                      {moodEmojis[payload.mood - 1] ?? ""}
                    </text>
                  );
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </DashCard>
  );
}

// ============ 身体数据卡片 ============

function BodyStatsCard({
  body,
  longestStreak,
}: {
  body: BodyStats | null;
  longestStreak: number;
}) {
  const rows = [
    {
      label: "当前体重",
      value: body?.current_weight_kg ? `${body.current_weight_kg} kg` : "未记录",
    },
    {
      label: "身高",
      value: body?.height_cm ? `${body.height_cm} cm` : "未记录",
    },
    {
      label: "最长连续",
      value: `${longestStreak} 天`,
    },
  ];

  return (
    <DashCard icon={<Scale className="size-4 text-sky-500" />} title="身体数据">
      <div className="flex h-full flex-col justify-center gap-2 sm:gap-3">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex flex-col gap-1 rounded-lg bg-emerald-50/60 px-3 py-2 sm:flex-row sm:items-center sm:justify-between sm:px-4 sm:py-3"
          >
            <span className="text-xs text-emerald-700 sm:text-sm">{row.label}</span>
            <span className="text-base font-bold text-emerald-950 sm:text-lg">{row.value}</span>
          </div>
        ))}
      </div>
    </DashCard>
  );
}

// ============ 主页面 ============

export default function DashboardPage() {
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [weekly, setWeekly] = useState<WeeklyStats | null>(null);
  const [body, setBody] = useState<BodyStats | null>(null);
  const [checkins, setCheckins] = useState<CheckinItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<OverviewStats>("/stats/overview").catch(() => null),
      api.get<WeeklyStats>("/stats/weekly").catch(() => null),
      api.get<BodyStats>("/stats/body").catch(() => null),
      api.get<{ items: CheckinItem[] }>("/checkins?size=50").catch(() => null),
    ]).then(([ov, wk, bd, checkinRes]) => {
      setOverview(ov);
      setWeekly(wk);
      setBody(bd);
      if (checkinRes?.items) {
        setCheckins(checkinRes.items);
      }
      setLoading(false);
    });
  }, []);

  const todayStr = format(new Date(), "yyyy-MM-dd");
  const todayCheckin = useMemo(
    () => checkins.find((c) => c.date === todayStr) || null,
    [checkins, todayStr]
  );

  const weeklyTotal = weekly?.total_duration_min ?? 0;
  const weeklyGoal = 300;
  const goalPercent = Math.min(100, Math.round((weeklyTotal / weeklyGoal) * 100));

  const trainingData = (weekly?.daily_breakdown ?? []).map((d, i) => ({
    day: dayLabels[i] ?? d.date,
    minutes: d.duration_min,
  }));

  const stats = [
    {
      label: "连续打卡",
      value: `${overview?.current_streak ?? 0} 天`,
      icon: Flame,
      color: "text-orange-500",
      bg: "bg-orange-100",
    },
    {
      label: "本周训练",
      value: `${weekly?.total_workouts ?? 0} 次`,
      icon: Dumbbell,
      color: "text-emerald-500",
      bg: "bg-emerald-100",
    },
    {
      label: "当前体重",
      value: body?.current_weight_kg ? `${body.current_weight_kg} kg` : "未记录",
      icon: Target,
      color: "text-sky-500",
      bg: "bg-sky-100",
    },
    {
      label: "累计训练",
      value: `${overview?.total_workouts ?? 0} 次`,
      icon: TrendingUp,
      color: "text-violet-500",
      bg: "bg-violet-100",
    },
  ];

  const avgDuration =
    weekly && weekly.total_workouts > 0
      ? Math.round(weekly.total_duration_min / weekly.total_workouts)
      : 0;

  return (
    <AppLayout>
      <div className="flex h-full flex-col overflow-hidden">
        {/* 顶部区域 */}
        <header className="border-b border-emerald-100 bg-white/70 px-4 py-3 backdrop-blur sm:px-6 sm:py-4">
          <div className="mx-auto flex max-w-7xl items-center justify-between gap-3">
            <div className="min-w-0">
              <h1 className="truncate text-lg font-bold tracking-tight text-emerald-950 sm:text-xl">
                {format(new Date(), "M月d日 EEEE", { locale: zhCN })}
              </h1>
              <p className="mt-0.5 truncate text-xs text-emerald-600/60 sm:text-sm">
                坚持就是胜利，今天也要加油 💪
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 sm:gap-2 sm:px-4 sm:py-2">
              <Zap className="size-3.5 text-emerald-500 sm:size-4" />
              <span className="whitespace-nowrap text-xs font-medium text-emerald-700 sm:text-sm">
                本周训练 {weeklyTotal} 分钟
              </span>
            </div>
          </div>
        </header>

        {/* 主内容区 */}
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-32 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : (
            <div className="mx-auto max-w-7xl space-y-4 p-4 sm:space-y-6 sm:p-6">
              {/* 今日概览条：热量环形图 + 三大营养素 + 缺口提示 */}
              <TodayOverviewBar
                trainingCalories={todayCheckin?.calories_burned ?? null}
                trainingDuration={todayCheckin?.duration_min ?? null}
              />

              {/* 第一行：统计小卡片 */}
              <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
                {stats.map((stat) => (
                  <Card
                    key={stat.label}
                    className="group border-emerald-100 bg-white/80 shadow-sm backdrop-blur transition-all duration-200 hover:border-emerald-200 hover:shadow-md"
                  >
                    <CardContent className="flex items-center gap-3 p-3 sm:p-4">
                      <div className={cn("flex size-9 shrink-0 items-center justify-center rounded-xl transition-transform duration-200 group-hover:scale-110 sm:size-10", stat.bg)}>
                        <stat.icon className={cn("size-4 sm:size-5", stat.color)} />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-xs text-emerald-600/60">{stat.label}</p>
                        <p className="truncate text-base font-bold tabular-nums text-emerald-950 sm:text-lg">{stat.value}</p>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* 第二行起：6 个大方块，手机每行 2 个 / PC 每行 3 个 */}
              <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-3 lg:gap-5">
                <TodayTraining checkin={todayCheckin} />
                <NutritionCard />
                <WeeklyGoalCard
                  weekly={weekly}
                  goalPercent={goalPercent}
                  weeklyTotal={weeklyTotal}
                  avgDuration={avgDuration}
                />
                <WeeklyVolumeCard data={trainingData} total={weeklyTotal} />
                <MoodTrendCard checkins={checkins} />
                <BodyStatsCard body={body} longestStreak={overview?.longest_streak ?? 0} />
              </div>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
