import { useState, useMemo, useEffect } from "react";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AppLayout } from "@/components/app-layout";
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
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

// ============ 数据类型 ============

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
  duration_min: number;
  mood: number | null;
  note: string | null;
  exercises: CheckinExercise[];
}

const dayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const moodEmojis = ["😫", "😕", "😐", "🙂", "🤩"];

// ============ 今日训练卡片 ============

function TodayTraining({ checkin }: { checkin: CheckinItem | null }) {
  return (
    <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-emerald-950">
          <Dumbbell className="size-4 text-emerald-500" />
          今日训练
        </CardTitle>
      </CardHeader>
      <CardContent>
        {checkin ? (
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-lg bg-emerald-50/60 px-4 py-3">
              <span className="text-sm text-emerald-700">训练时长</span>
              <span className="flex items-center gap-1.5 text-lg font-bold text-emerald-950">
                <Clock className="size-4 text-emerald-500" />
                {checkin.duration_min} 分钟
              </span>
            </div>
            {checkin.mood && (
              <div className="flex items-center justify-between rounded-lg bg-emerald-50/60 px-4 py-3">
                <span className="text-sm text-emerald-700">心情评分</span>
                <span className="flex items-center gap-1.5 text-lg font-bold text-emerald-950">
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
                    className="flex items-center justify-between rounded-lg bg-emerald-50/40 px-3 py-2 text-sm"
                  >
                    <span className="font-medium text-emerald-900">
                      {ex.exercise_name ?? "未知动作"}
                    </span>
                    <span className="tabular-nums text-emerald-600/70">
                      {ex.sets_done ?? "-"} 组 × {ex.reps_done ?? "-"} 次
                      {ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {checkin.note && (
              <div className="flex items-start gap-2 rounded-lg bg-emerald-50/40 px-3 py-2 text-sm text-emerald-700">
                <StickyNote className="mt-0.5 size-3.5 shrink-0 text-emerald-400" />
                <span>{checkin.note}</span>
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-3 py-8 text-center">
            <Dumbbell className="size-8 text-emerald-200" />
            <p className="text-sm text-emerald-600/60">今天还没有训练记录</p>
            <p className="text-xs text-emerald-500/50">去 AI 教练那里获取今日训练建议吧</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ============ 饮食卡路里卡片 ============

function NutritionCard() {
  // 由于后端暂无饮食记录接口，这里展示目标卡路里和简单提示
  const targetCalories = 2000;
  const consumedCalories = 0; // 暂无数据
  const percent = Math.min(100, Math.round((consumedCalories / targetCalories) * 100));

  return (
    <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-emerald-950">
          <Apple className="size-4 text-emerald-500" />
          饮食记录
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative mx-auto size-32">
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
            <span className="text-2xl font-bold tabular-nums text-emerald-950">{consumedCalories}</span>
            <span className="text-xs text-emerald-600/60">/ {targetCalories} kcal</span>
          </div>
        </div>
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between rounded-lg bg-amber-50/60 px-4 py-3">
            <span className="flex items-center gap-2 text-sm text-amber-700">
              <Utensils className="size-4 text-amber-500" />
              目标摄入
            </span>
            <span className="text-lg font-bold text-amber-950">{targetCalories} kcal</span>
          </div>
          <div className="flex items-center justify-between rounded-lg bg-emerald-50/60 px-4 py-3">
            <span className="flex items-center gap-2 text-sm text-emerald-700">
              <Flame className="size-4 text-emerald-500" />
              已摄入
            </span>
            <span className="text-lg font-bold text-emerald-950">{consumedCalories} kcal</span>
          </div>
        </div>
        <p className="mt-3 text-center text-xs text-emerald-500/50">
          饮食记录功能开发中，可通过 AI 教练获取饮食建议
        </p>
      </CardContent>
    </Card>
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
      api.get<{ items: CheckinItem[] }>("/checkins?limit=50").catch(() => null),
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
        <header className="border-b border-emerald-100 bg-white/70 px-6 py-4 backdrop-blur">
          <div className="mx-auto flex max-w-7xl items-center justify-between">
            <div>
              <h1 className="text-xl font-bold tracking-tight text-emerald-950">
                {format(new Date(), "M月d日 EEEE", { locale: zhCN })}
              </h1>
              <p className="mt-0.5 text-sm text-emerald-600/60">坚持就是胜利，今天也要加油 💪</p>
            </div>
            <div className="flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2">
              <Zap className="size-4 text-emerald-500" />
              <span className="text-sm font-medium text-emerald-700">
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
            <div className="mx-auto max-w-7xl space-y-6 p-6">
              {/* 统计卡片 */}
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                {stats.map((stat) => (
                  <Card
                    key={stat.label}
                    className="group border-emerald-100 bg-white/80 shadow-sm backdrop-blur transition-all duration-200 hover:border-emerald-200 hover:shadow-md"
                  >
                    <CardContent className="flex items-center gap-3 p-4">
                      <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl transition-transform duration-200 group-hover:scale-110", stat.bg)}>
                        <stat.icon className={cn("size-5", stat.color)} />
                      </div>
                      <div>
                        <p className="text-xs text-emerald-600/60">{stat.label}</p>
                        <p className="text-lg font-bold tabular-nums text-emerald-950">{stat.value}</p>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* 两栏布局：今日训练 + 饮食 */}
              <div className="grid gap-6 lg:grid-cols-2">
                <TodayTraining checkin={todayCheckin} />
                <NutritionCard />
              </div>

              {/* 本周目标 + 身体数据 */}
              <div className="grid gap-6 lg:grid-cols-2">
                <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                  <CardHeader className="pb-2">
                    <CardTitle className="flex items-center gap-2 text-base font-semibold text-emerald-950">
                      <Target className="size-4 text-emerald-500" />
                      本周目标
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="relative mx-auto size-40">
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
                        <span className="text-3xl font-bold tabular-nums text-emerald-950">{goalPercent}%</span>
                        <span className="text-xs text-emerald-600/60">{weeklyTotal}/{weeklyGoal} 分钟</span>
                      </div>
                    </div>
                    <div className="mt-4 space-y-2">
                      <div className="flex justify-between text-sm">
                        <span className="text-emerald-600/60">训练次数</span>
                        <span className="font-medium text-emerald-950">{weekly?.total_workouts ?? 0} 次</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-emerald-600/60">完成组数</span>
                        <span className="font-medium text-emerald-950">{weekly?.total_sets ?? 0} 组</span>
                      </div>
                      <div className="flex justify-between text-sm">
                        <span className="text-emerald-600/60">平均时长</span>
                        <span className="font-medium text-emerald-950">{avgDuration} 分钟/次</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                  <CardHeader className="pb-2">
                    <CardTitle className="text-base font-semibold text-emerald-950">身体数据</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="flex items-center justify-between rounded-lg bg-emerald-50/60 px-4 py-3">
                      <span className="text-sm text-emerald-700">当前体重</span>
                      <span className="text-lg font-bold text-emerald-950">
                        {body?.current_weight_kg ? `${body.current_weight_kg} kg` : "未记录"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between rounded-lg bg-emerald-50/60 px-4 py-3">
                      <span className="text-sm text-emerald-700">身高</span>
                      <span className="text-lg font-bold text-emerald-950">
                        {body?.height_cm ? `${body.height_cm} cm` : "未记录"}
                      </span>
                    </div>
                    <div className="flex items-center justify-between rounded-lg bg-emerald-50/60 px-4 py-3">
                      <span className="text-sm text-emerald-700">最长连续</span>
                      <span className="text-lg font-bold text-emerald-950">
                        {overview?.longest_streak ?? 0} 天
                      </span>
                    </div>
                  </CardContent>
                </Card>
              </div>

              {/* 图表区域 */}
              <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-semibold text-emerald-950">本周训练量</CardTitle>
                    <span className="text-xs text-emerald-600/60">总计 {weeklyTotal} 分钟</span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="h-56">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={trainingData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#d1fae5" vertical={false} />
                        <XAxis dataKey="day" tick={{ fill: "#6ee7b7", fontSize: 11 }} axisLine={false} tickLine={false} />
                        <YAxis tick={{ fill: "#6ee7b7", fontSize: 11 }} axisLine={false} tickLine={false} />
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
                </CardContent>
              </Card>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}