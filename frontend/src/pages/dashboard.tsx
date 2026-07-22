import { useState, useMemo, useEffect } from "react";
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
import {
  AreaChart,
  Area,
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
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AppLayout } from "@/components/app-layout";
import {
  ChevronLeft,
  ChevronRight,
  Flame,
  Dumbbell,
  Target,
  TrendingUp,
  CalendarDays,
  Zap,
  Loader2,
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

interface CheckinItem {
  id: string;
  date: string;
  duration_min: number;
}

const dayLabels = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

// ============ 日历组件 ============

function CheckinCalendar({ checkinDates }: { checkinDates: Set<string> }) {
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
            <Button variant="ghost" size="icon" className="size-7 text-emerald-700 hover:bg-emerald-100" onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}>
              <ChevronLeft className="size-4" />
            </Button>
            <span className="min-w-20 text-center text-sm font-medium text-emerald-900">
              {format(currentMonth, "yyyy年M月", { locale: zhCN })}
            </span>
            <Button variant="ghost" size="icon" className="size-7 text-emerald-700 hover:bg-emerald-100" onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}>
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-2 grid grid-cols-7 text-center text-xs font-medium text-emerald-600/60">
          {["一", "二", "三", "四", "五", "六", "日"].map((d) => (
            <div key={d} className="py-1">{d}</div>
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
                  checked && "bg-emerald-100 text-emerald-700 font-medium hover:bg-emerald-200",
                  isSelected && "ring-2 ring-emerald-400",
                  isToday(day) && "font-bold text-emerald-950",
                  isFuture && "opacity-40"
                )}
              >
                {format(day, "d")}
                {checked && <span className="absolute bottom-1 size-1 rounded-full bg-emerald-500" />}
              </button>
            );
          })}
        </div>
        <div className="mt-4 flex items-center justify-between rounded-lg bg-emerald-50 px-3 py-2">
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
      </CardContent>
    </Card>
  );
}

// ============ 主页面 ============

export default function DashboardPage() {
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [weekly, setWeekly] = useState<WeeklyStats | null>(null);
  const [body, setBody] = useState<BodyStats | null>(null);
  const [checkinDates, setCheckinDates] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<OverviewStats>("/stats/overview").catch(() => null),
      api.get<WeeklyStats>("/stats/weekly").catch(() => null),
      api.get<BodyStats>("/stats/body").catch(() => null),
      api.get<{ items: CheckinItem[] }>("/checkins?limit=200").catch(() => null),
    ]).then(([ov, wk, bd, checkins]) => {
      setOverview(ov);
      setWeekly(wk);
      setBody(bd);
      if (checkins?.items) {
        setCheckinDates(new Set(checkins.items.map((c) => c.date)));
      }
      setLoading(false);
    });
  }, []);

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

              {/* 三栏布局 */}
              <div className="grid gap-6 lg:grid-cols-3">
                <div className="lg:col-span-1">
                  <CheckinCalendar checkinDates={checkinDates} />
                </div>

                <div className="lg:col-span-1">
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
                </div>

                <div className="lg:col-span-1">
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
              </div>

              {/* 图表区域 */}
              <div className="grid gap-6 lg:grid-cols-1">
                {/* 训练量统计 */}
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
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}