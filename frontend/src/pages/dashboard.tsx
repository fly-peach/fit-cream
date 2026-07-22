import { useState, useMemo } from "react";
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
import { Progress } from "@/components/ui/progress";
import {
  ChevronLeft,
  ChevronRight,
  Flame,
  Dumbbell,
  Target,
  TrendingUp,
  CalendarDays,
  CheckCircle2,
  Circle,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

// ============ Mock 数据 (后续接入后端 API) ============

interface TodoItem {
  id: string;
  title: string;
  detail: string;
  time: string;
  type: "training" | "meal" | "checkin";
  completed: boolean;
}

const initialTodos: TodoItem[] = [
  { id: "1", title: "胸部 + 三头训练", detail: "卧推 4x8 · 飞鸟 3x12 · 臂屈伸 3x15", time: "07:00", type: "training", completed: true },
  { id: "2", title: "蛋白质摄入 30g", detail: "早餐：鸡蛋 3 个 + 牛奶 300ml", time: "08:00", type: "meal", completed: true },
  { id: "3", title: "有氧 30 分钟", detail: "慢跑或椭圆机，心率保持 130-150", time: "18:00", type: "training", completed: false },
  { id: "4", title: "晚餐打卡", detail: "低脂饮食，碳水控制在 50g 以内", time: "19:30", type: "checkin", completed: false },
  { id: "5", title: "体重记录", detail: "空腹晨重，记录到打卡日历", time: "21:00", type: "checkin", completed: false },
];

// 打卡记录 (最近 3 个月)
const checkinDates = new Set<string>();
const today = new Date();
for (let i = 0; i < 90; i++) {
  const d = new Date(today);
  d.setDate(d.getDate() - i);
  // 模拟 70% 打卡率
  if (Math.random() < 0.7) {
    checkinDates.add(format(d, "yyyy-MM-dd"));
  }
}
checkinDates.add(format(today, "yyyy-MM-dd"));

// 体重趋势数据
const weightData = Array.from({ length: 12 }, (_, i) => {
  const week = new Date(today);
  week.setDate(week.getDate() - (11 - i) * 7);
  return {
    week: format(week, "MM/dd"),
    weight: +(78 - i * 0.4 + Math.random() * 0.6).toFixed(1),
    target: 72,
  };
});

// 每周训练量数据
const trainingData = [
  { day: "周一", minutes: 65, calories: 420 },
  { day: "周二", minutes: 45, calories: 310 },
  { day: "周三", minutes: 0, calories: 0 },
  { day: "周四", minutes: 70, calories: 480 },
  { day: "周五", minutes: 50, calories: 350 },
  { day: "周六", minutes: 85, calories: 560 },
  { day: "周日", minutes: 30, calories: 180 },
];

const typeConfig = {
  training: { label: "训练", color: "bg-emerald-500/15 text-emerald-400 border-emerald-500/20" },
  meal: { label: "饮食", color: "bg-amber-500/15 text-amber-400 border-amber-500/20" },
  checkin: { label: "打卡", color: "bg-sky-500/15 text-sky-400 border-sky-500/20" },
};

// ============ 日历组件 ============

function CheckinCalendar() {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState(new Date());

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
  }, [calendarDays, currentMonth]);

  const selectedChecked = checkinDates.has(format(selectedDate, "yyyy-MM-dd"));

  return (
    <Card className="border-zinc-800 bg-zinc-900/60 backdrop-blur">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <CalendarDays className="size-4 text-emerald-400" />
            打卡日历
          </CardTitle>
          <div className="flex items-center gap-1">
            <Button variant="ghost" size="icon" className="size-7" onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}>
              <ChevronLeft className="size-4" />
            </Button>
            <span className="min-w-20 text-center text-sm font-medium">
              {format(currentMonth, "yyyy年M月", { locale: zhCN })}
            </span>
            <Button variant="ghost" size="icon" className="size-7" onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}>
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {/* 星期标题 */}
        <div className="mb-2 grid grid-cols-7 text-center text-xs text-zinc-500">
          {["一", "二", "三", "四", "五", "六", "日"].map((d) => (
            <div key={d} className="py-1">{d}</div>
          ))}
        </div>
        {/* 日期格子 */}
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
                  !inMonth && "text-zinc-700",
                  inMonth && !checked && !isSelected && "text-zinc-400 hover:bg-zinc-800",
                  checked && "bg-emerald-500/20 text-emerald-300 font-medium hover:bg-emerald-500/30",
                  isSelected && "ring-2 ring-emerald-400",
                  isToday(day) && "font-bold text-white",
                  isFuture && "opacity-40"
                )}
              >
                {format(day, "d")}
                {checked && <span className="absolute bottom-1 size-1 rounded-full bg-emerald-400" />}
              </button>
            );
          })}
        </div>
        {/* 统计 */}
        <div className="mt-4 flex items-center justify-between rounded-lg bg-zinc-800/50 px-3 py-2">
          <span className="text-xs text-zinc-400">
            {format(selectedDate, "M月d日", { locale: zhCN })}
            {selectedChecked ? (
              <span className="ml-2 text-emerald-400">✓ 已打卡</span>
            ) : (
              <span className="ml-2 text-zinc-500">未打卡</span>
            )}
          </span>
          <span className="text-xs text-zinc-400">
            本月 <span className="font-semibold text-emerald-400">{monthCheckins}</span> 天
          </span>
        </div>
      </CardContent>
    </Card>
  );
}

// ============ 待办列表组件 ============

function TodoList() {
  const [todos, setTodos] = useState<TodoItem[]>(initialTodos);
  const completedCount = todos.filter((t) => t.completed).length;
  const progressPercent = Math.round((completedCount / todos.length) * 100);

  const toggleTodo = (id: string) => {
    setTodos((prev) => prev.map((t) => (t.id === id ? { ...t, completed: !t.completed } : t)));
  };

  return (
    <Card className="border-zinc-800 bg-zinc-900/60 backdrop-blur">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base font-semibold">
            <CheckCircle2 className="size-4 text-emerald-400" />
            今日待办
          </CardTitle>
          <Badge variant="secondary" className="bg-emerald-500/15 text-emerald-400 border-emerald-500/20">
            {completedCount}/{todos.length}
          </Badge>
        </div>
        <Progress value={progressPercent} className="mt-2 h-1.5 bg-zinc-800" />
      </CardHeader>
      <CardContent className="space-y-1">
        {todos.map((todo) => (
          <div
            key={todo.id}
            onClick={() => toggleTodo(todo.id)}
            className={cn(
              "group flex cursor-pointer items-start gap-3 rounded-xl px-3 py-2.5 transition-all duration-150",
              "hover:bg-zinc-800/60",
              todo.completed && "opacity-60"
            )}
          >
            <button className="mt-0.5 shrink-0">
              {todo.completed ? (
                <CheckCircle2 className="size-5 text-emerald-400 transition-transform group-hover:scale-110" />
              ) : (
                <Circle className="size-5 text-zinc-600 transition-colors group-hover:text-zinc-400" />
              )}
            </button>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className={cn("text-sm font-medium", todo.completed && "line-through text-zinc-500")}>
                  {todo.title}
                </span>
                <Badge className={cn("text-[10px] px-1.5 py-0 border", typeConfig[todo.type].color)}>
                  {typeConfig[todo.type].label}
                </Badge>
              </div>
              <p className={cn("mt-0.5 text-xs text-zinc-500", todo.completed && "line-through")}>
                {todo.detail}
              </p>
            </div>
            <span className="shrink-0 text-xs tabular-nums text-zinc-600">{todo.time}</span>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ============ 主页面 ============

export default function DashboardPage() {
  const stats = [
    { label: "连续打卡", value: "12 天", icon: Flame, color: "text-orange-400", bg: "bg-orange-500/10" },
    { label: "本周训练", value: "5 次", icon: Dumbbell, color: "text-emerald-400", bg: "bg-emerald-500/10" },
    { label: "当前体重", value: "74.2 kg", icon: Target, color: "text-sky-400", bg: "bg-sky-500/10" },
    { label: "距目标", value: "-2.2 kg", icon: TrendingUp, color: "text-violet-400", bg: "bg-violet-500/10" },
  ];

  const weeklyTotal = trainingData.reduce((sum, d) => sum + d.minutes, 0);
  const weeklyGoal = 300; // 每周 300 分钟目标
  const goalPercent = Math.min(100, Math.round((weeklyTotal / weeklyGoal) * 100));

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-zinc-950">
      {/* 顶部区域 */}
      <header className="border-b border-zinc-800/80 bg-zinc-900/40 px-6 py-4 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div>
            <h1 className="text-xl font-bold tracking-tight">
              {format(new Date(), "M月d日 EEEE", { locale: zhCN })}
            </h1>
            <p className="mt-0.5 text-sm text-zinc-500">坚持就是胜利，今天也要加油 💪</p>
          </div>
          <div className="flex items-center gap-2 rounded-full bg-emerald-500/10 px-4 py-2 border border-emerald-500/20">
            <Zap className="size-4 text-emerald-400" />
            <span className="text-sm font-medium text-emerald-300">今日已消耗 320 kcal</span>
          </div>
        </div>
      </header>

      {/* 主内容区 */}
      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-7xl space-y-6 p-6">
          {/* 统计卡片 */}
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {stats.map((stat) => (
              <Card
                key={stat.label}
                className="group border-zinc-800 bg-zinc-900/60 backdrop-blur transition-all duration-200 hover:border-zinc-700 hover:bg-zinc-900"
              >
                <CardContent className="flex items-center gap-3 p-4">
                  <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl transition-transform duration-200 group-hover:scale-110", stat.bg)}>
                    <stat.icon className={cn("size-5", stat.color)} />
                  </div>
                  <div>
                    <p className="text-xs text-zinc-500">{stat.label}</p>
                    <p className="text-lg font-bold tabular-nums">{stat.value}</p>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* 三栏布局 */}
          <div className="grid gap-6 lg:grid-cols-3">
            {/* 左栏：待办列表 */}
            <div className="lg:col-span-1">
              <TodoList />
            </div>

            {/* 中栏：日历 */}
            <div className="lg:col-span-1">
              <CheckinCalendar />
            </div>

            {/* 右栏：周目标完成度 */}
            <div className="lg:col-span-1">
              <Card className="border-zinc-800 bg-zinc-900/60 backdrop-blur">
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center gap-2 text-base font-semibold">
                    <Target className="size-4 text-emerald-400" />
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
                        <RadialBar background={{ fill: "#27272a" }} cornerRadius={10} dataKey="value" />
                      </RadialBarChart>
                    </ResponsiveContainer>
                    <div className="absolute inset-0 flex flex-col items-center justify-center">
                      <span className="text-3xl font-bold tabular-nums">{goalPercent}%</span>
                      <span className="text-xs text-zinc-500">{weeklyTotal}/{weeklyGoal} 分钟</span>
                    </div>
                  </div>
                  <div className="mt-4 space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-500">训练次数</span>
                      <span className="font-medium">5/6 次</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-500">消耗热量</span>
                      <span className="font-medium">2,300 kcal</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-zinc-500">平均时长</span>
                      <span className="font-medium">58 分钟/次</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          {/* 图表区域 */}
          <div className="grid gap-6 lg:grid-cols-2">
            {/* 体重趋势 */}
            <Card className="border-zinc-800 bg-zinc-900/60 backdrop-blur">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-semibold">体重趋势</CardTitle>
                  <Badge variant="secondary" className="bg-emerald-500/15 text-emerald-400 border-emerald-500/20">
                    12 周 -3.8kg
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={weightData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                      <defs>
                        <linearGradient id="weightGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#10b981" stopOpacity={0.3} />
                          <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                      <XAxis dataKey="week" tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[70, 80]} tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#18181b",
                          border: "1px solid #3f3f46",
                          borderRadius: "12px",
                          fontSize: "12px",
                        }}
                        labelStyle={{ color: "#a1a1aa" }}
                      />
                      <Area
                        type="monotone"
                        dataKey="weight"
                        name="体重 (kg)"
                        stroke="#10b981"
                        strokeWidth={2}
                        fill="url(#weightGradient)"
                        dot={{ r: 3, fill: "#10b981", strokeWidth: 0 }}
                        activeDot={{ r: 5 }}
                      />
                      <Area
                        type="monotone"
                        dataKey="target"
                        name="目标"
                        stroke="#71717a"
                        strokeWidth={1}
                        strokeDasharray="5 5"
                        fill="none"
                        dot={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>

            {/* 训练量统计 */}
            <Card className="border-zinc-800 bg-zinc-900/60 backdrop-blur">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base font-semibold">本周训练量</CardTitle>
                  <span className="text-xs text-zinc-500">总计 {weeklyTotal} 分钟</span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={trainingData} margin={{ top: 10, right: 10, left: -15, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
                      <XAxis dataKey="day" tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <YAxis tick={{ fill: "#71717a", fontSize: 11 }} axisLine={false} tickLine={false} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: "#18181b",
                          border: "1px solid #3f3f46",
                          borderRadius: "12px",
                          fontSize: "12px",
                        }}
                        labelStyle={{ color: "#a1a1aa" }}
                        cursor={{ fill: "#27272a", opacity: 0.5 }}
                      />
                      <Bar dataKey="minutes" name="时长 (分钟)" fill="#10b981" radius={[6, 6, 0, 0]} maxBarSize={32} />
                      <Bar dataKey="calories" name="热量 (kcal)" fill="#f59e0b" radius={[6, 6, 0, 0]} maxBarSize={32} opacity={0.7} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}