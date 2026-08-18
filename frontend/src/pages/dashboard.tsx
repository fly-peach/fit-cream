import { useState, useMemo, useEffect, useRef, type ReactNode } from "react";
import {
  format,
  parseISO,
  subDays,
  startOfMonth,
  startOfDay,
  eachDayOfInterval,
} from "date-fns";
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
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  BarChart3,
  Scale,
  Pencil,
  Check,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

// ============ 数据类型 ============

interface UserSettings {
  calorie_goal: number;
  protein_goal_g: number;
  carbs_goal_g: number;
  fat_goal_g: number;
  weekly_training_goal: number;
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

const moodEmojis = ["😫", "😕", "😐", "🙂", "🤩"];

interface MoodLogItem {
  id: string;
  date: string;
  mood: number;
  note: string | null;
}

type VolumeRange = "7d" | "30d" | "90d" | "month";

const volumeRangeOptions: { value: VolumeRange; label: string }[] = [
  { value: "7d", label: "近7天" },
  { value: "30d", label: "近30天" },
  { value: "90d", label: "近90天" },
  { value: "month", label: "本月" },
];

function computeVolumeRange(range: VolumeRange): { start: Date; end: Date } {
  const today = new Date();
  if (range === "7d") return { start: subDays(today, 6), end: today };
  if (range === "30d") return { start: subDays(today, 29), end: today };
  if (range === "90d") return { start: subDays(today, 89), end: today };
  return { start: startOfMonth(today), end: today };
}

function aggregateVolume(
  items: CheckinItem[],
  range: VolumeRange,
): { day: string; minutes: number }[] {
  const { start, end } = computeVolumeRange(range);
  const byDate = new Map<string, number>();
  for (const c of items) {
    if (c.duration_min != null) {
      byDate.set(c.date, (byDate.get(c.date) ?? 0) + c.duration_min);
    }
  }
  const days = eachDayOfInterval({ start: startOfDay(start), end: startOfDay(end) });
  if (range !== "90d" && range !== "month") {
    return days.map((d) => ({
      day: format(d, "M/d"),
      minutes: byDate.get(format(d, "yyyy-MM-dd")) ?? 0,
    }));
  }
  const out: { day: string; minutes: number }[] = [];
  for (let i = 0; i < days.length; i += 7) {
    const week = days.slice(i, i + 7);
    const sum = week.reduce(
      (acc, d) => acc + (byDate.get(format(d, "yyyy-MM-dd")) ?? 0),
      0,
    );
    out.push({ day: format(week[0], "M/d"), minutes: sum });
  }
  return out;
}

function formatDuration(min: number): string {
  if (min >= 60) {
    const h = Math.floor(min / 60);
    const m = min % 60;
    return m > 0 ? `${h} 小时 ${m} 分` : `${h} 小时`;
  }
  return `${min} 分钟`;
}

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
      <CardHeader className="p-3 pb-2 sm:p-6 sm:pb-3">
        <CardTitle className="flex min-w-0 items-center gap-1.5 text-sm font-semibold text-emerald-950 sm:gap-2 sm:text-base">
          {icon}
          <span className="min-w-0 flex-1 truncate">{title}</span>
          {action}
        </CardTitle>
      </CardHeader>
      <CardContent className="flex-1 p-3 pt-1 sm:p-6 sm:pt-1">{children}</CardContent>
    </Card>
  );
}

// ============ 今日训练卡片 ============

function TodayTraining({ checkin }: { checkin: CheckinItem | null }) {
  return (
    <DashCard icon={<Dumbbell className="size-4 text-emerald-500" />} title="今日训练">
      {checkin ? (
        <div className="space-y-1.5 sm:space-y-3">
          {checkin.duration_min != null && (
            <div className="flex flex-col gap-0.5 rounded-lg bg-emerald-50/60 px-2 py-1.5 sm:flex-row sm:items-center sm:justify-between sm:gap-1 sm:px-4 sm:py-3">
              <span className="text-[11px] text-emerald-700 sm:text-sm">训练时长</span>
              <span className="flex items-center gap-1 text-sm font-bold text-emerald-950 sm:gap-1.5 sm:text-lg">
                <Clock className="size-3.5 text-emerald-500 sm:size-4" />
                {checkin.duration_min} 分钟
              </span>
            </div>
          )}
          {checkin.mood && (
            <div className="flex flex-col gap-0.5 rounded-lg bg-emerald-50/60 px-2 py-1.5 sm:flex-row sm:items-center sm:justify-between sm:gap-1 sm:px-4 sm:py-3">
              <span className="text-[11px] text-emerald-700 sm:text-sm">心情评分</span>
              <span className="flex items-center gap-1 text-sm font-bold text-emerald-950 sm:gap-1.5 sm:text-lg">
                <Smile className="size-3.5 text-emerald-500 sm:size-4" />
                {moodEmojis[checkin.mood - 1]}
              </span>
            </div>
          )}
          {checkin.exercises.length > 0 && (
            <div className="space-y-1">
              <p className="text-[11px] font-medium text-emerald-600/60 sm:text-xs">训练动作</p>
              {checkin.exercises.map((ex) => (
                <div
                  key={ex.id}
                  className="rounded-lg bg-emerald-50/40 px-2 py-1.5 sm:flex sm:items-center sm:justify-between sm:gap-2 sm:px-3 sm:py-2"
                >
                  <span className="block truncate text-[11px] font-medium text-emerald-900 sm:text-sm">
                    {ex.exercise_name ?? "未知动作"}
                  </span>
                  <span className="text-[10px] tabular-nums text-emerald-600/70 sm:shrink-0 sm:text-xs">
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

// ============ 本周目标卡片 ============

function WeeklyGoalCard({
  weekly,
  goalPercent,
  goal,
  onGoalChange,
}: {
  weekly: WeeklyStats | null;
  goalPercent: number;
  goal: number;
  onGoalChange: (goal: number) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const editInputRef = useRef<HTMLInputElement>(null);

  const totalWorkouts = weekly?.total_workouts ?? 0;

  useEffect(() => {
    if (editing && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editing]);

  const startEdit = () => {
    setEditing(true);
    setEditValue(String(goal));
  };

  const cancelEdit = () => {
    setEditing(false);
    setEditValue("");
  };

  const saveEdit = async () => {
    const num = parseInt(editValue, 10);
    if (isNaN(num) || num < 1 || num > 14) {
      cancelEdit();
      return;
    }
    setSaving(true);
    try {
      const updated = await api.put<UserSettings>("/users/settings", {
        weekly_training_goal: num,
      });
      if (updated?.weekly_training_goal != null) {
        onGoalChange(updated.weekly_training_goal);
      }
    } catch {
      // silent
    } finally {
      setSaving(false);
      setEditing(false);
    }
  };

  return (
    <DashCard icon={<Target className="size-4 text-emerald-500" />} title="本周目标">
      <div className="relative mx-auto size-20 sm:size-28 lg:size-36">
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
          <span className="text-xl font-bold tabular-nums text-emerald-950 sm:text-2xl lg:text-3xl">
            {goalPercent}%
          </span>
          {editing ? (
            <span className="flex items-center gap-0.5">
              <span className="text-[10px] tabular-nums text-emerald-600/70">{totalWorkouts}/</span>
              <input
                ref={editInputRef}
                type="number"
                min={1}
                max={14}
                step={1}
                value={editValue}
                onChange={(e) => setEditValue(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    saveEdit();
                  } else if (e.key === "Escape") {
                    cancelEdit();
                  }
                }}
                disabled={saving}
                className="h-4 w-11 rounded border border-emerald-200 bg-white px-1 text-right text-[10px] tabular-nums text-emerald-800 outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-200"
              />
              <span className="text-[10px] text-emerald-600/70">次</span>
              <button
                type="button"
                onClick={saveEdit}
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
              onClick={startEdit}
              className="group/target flex items-center gap-0.5 rounded px-0.5 text-[10px] text-emerald-600/60 transition-colors hover:bg-emerald-50 sm:text-xs"
              title="点击编辑周目标"
            >
              <span className="tabular-nums">
                {totalWorkouts}/{goal} 次
              </span>
              <Pencil className="size-2.5 text-emerald-300 opacity-100 transition-opacity sm:opacity-0 sm:group-hover/target:opacity-100" />
            </button>
          )}
        </div>
      </div>
      <div className="mt-2 space-y-1.5 sm:mt-4 sm:space-y-2">
        <div className="flex justify-between text-[11px] sm:text-sm">
          <span className="text-emerald-600/60">训练次数</span>
          <span className="font-medium text-emerald-950">{weekly?.total_workouts ?? 0} 次</span>
        </div>
        <div className="flex justify-between text-[11px] sm:text-sm">
          <span className="text-emerald-600/60">完成组数</span>
          <span className="font-medium text-emerald-950">{weekly?.total_sets ?? 0} 组</span>
        </div>
      </div>
    </DashCard>
  );
}

// ============ 训练量图表卡片（可切换时间区间） ============

function WeeklyVolumeCard() {
  const [range, setRange] = useState<VolumeRange>("7d");
  const [data, setData] = useState<{ day: string; minutes: number }[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const { start, end } = computeVolumeRange(range);
    api
      .get<{ items: CheckinItem[] }>(
        `/checkins?start=${format(start, "yyyy-MM-dd")}&end=${format(end, "yyyy-MM-dd")}&size=100`,
      )
      .then((res) => {
        if (!cancelled) setData(aggregateVolume(res?.items ?? [], range));
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [range]);

  return (
    <DashCard
      icon={<BarChart3 className="size-4 text-emerald-500" />}
      title="训练量"
      action={
        <div className="flex shrink-0 items-center gap-0.5 rounded-lg bg-emerald-50 p-0.5">
          {volumeRangeOptions.map((o) => (
            <button
              key={o.value}
              type="button"
              onClick={() => setRange(o.value)}
              className={cn(
                "rounded-md px-1.5 py-0.5 text-[10px] font-medium transition-colors sm:px-2 sm:text-xs",
                range === o.value
                  ? "bg-white text-emerald-700 shadow-sm"
                  : "text-emerald-600/60 hover:text-emerald-700",
              )}
            >
              {o.label}
            </button>
          ))}
        </div>
      }
    >
      {loading ? (
        <div className="flex h-32 items-center justify-center sm:h-44">
          <Loader2 className="size-5 animate-spin text-emerald-500" />
        </div>
      ) : (
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
      )}
    </DashCard>
  );
}

// ============ 心情记录对话框 ============

function MoodRecordDialog({
  open,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) setSelected(null);
  }, [open]);

  const save = async () => {
    if (selected == null) return;
    setSaving(true);
    try {
      await api.put("/moods", {
        date: format(new Date(), "yyyy-MM-dd"),
        mood: selected,
      });
      onSaved();
      onOpenChange(false);
    } catch {
      // silent
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>记录今天的心情</DialogTitle>
          <DialogDescription>选择最符合你现在感受的表情</DialogDescription>
        </DialogHeader>
        <div className="flex justify-center gap-2 py-2">
          {moodEmojis.map((emoji, i) => (
            <button
              key={emoji}
              type="button"
              onClick={() => setSelected(i + 1)}
              className={cn(
                "flex size-11 items-center justify-center rounded-full text-2xl transition-all",
                selected === i + 1
                  ? "scale-110 bg-amber-100 ring-2 ring-amber-400"
                  : "hover:bg-emerald-50",
              )}
            >
              {emoji}
            </button>
          ))}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button onClick={save} disabled={selected == null || saving}>
            {saving && <Loader2 className="mr-1 size-3.5 animate-spin" />}
            保存
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ============ 心情趋势图表卡片 ============

function MoodTrendCard({ checkins }: { checkins: CheckinItem[] }) {
  const [moods, setMoods] = useState<MoodLogItem[]>([]);
  const [dialogOpen, setDialogOpen] = useState(false);

  const loadMoods = () => {
    const start = format(subDays(new Date(), 29), "yyyy-MM-dd");
    const end = format(new Date(), "yyyy-MM-dd");
    api
      .get<MoodLogItem[]>(`/moods?start=${start}&end=${end}`)
      .then((res) => setMoods(res ?? []))
      .catch(() => {});
  };

  useEffect(() => {
    loadMoods();
  }, []);

  const moodData = useMemo(() => {
    const byDate = new Map<string, number>();
    for (const c of checkins) {
      if (c.mood != null) byDate.set(c.date, c.mood);
    }
    for (const m of moods) {
      byDate.set(m.date, m.mood);
    }
    return [...byDate.entries()]
      .map(([date, mood]) => ({ date, mood }))
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-10)
      .map(({ date, mood }) => ({
        label: format(parseISO(date), "M/d"),
        mood,
      }));
  }, [checkins, moods]);

  return (
    <DashCard
      icon={<Smile className="size-4 text-amber-500" />}
      title="心情趋势"
      action={
        <Button
          variant="ghost"
          size="sm"
          className="shrink-0 px-2 text-emerald-600 hover:bg-emerald-50"
          onClick={() => setDialogOpen(true)}
        >
          <Smile className="mr-1 size-3.5" />
          记录心情
        </Button>
      }
    >
      {moodData.length === 0 ? (
        <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 py-4 text-center sm:min-h-44">
          <span className="text-3xl">😐</span>
          <p className="text-xs text-emerald-600/60 sm:text-sm">还没有心情记录</p>
          <p className="text-[11px] text-emerald-500/50 sm:text-xs">
            点右上角「记录心情」记录今天的心情吧
          </p>
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
      <MoodRecordDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onSaved={loadMoods}
      />
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
      <div className="flex h-full flex-col justify-center gap-1.5 sm:gap-3">
        {rows.map((row) => (
          <div
            key={row.label}
            className="flex flex-col gap-0.5 rounded-lg bg-emerald-50/60 px-2 py-1.5 sm:flex-row sm:items-center sm:justify-between sm:gap-1 sm:px-4 sm:py-3"
          >
            <span className="text-[11px] text-emerald-700 sm:text-sm">{row.label}</span>
            <span className="text-sm font-bold text-emerald-950 sm:text-lg">{row.value}</span>
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
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [checkins, setCheckins] = useState<CheckinItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get<OverviewStats>("/stats/overview").catch(() => null),
      api.get<WeeklyStats>("/stats/weekly").catch(() => null),
      api.get<BodyStats>("/stats/body").catch(() => null),
      api.get<UserSettings>("/users/settings").catch(() => null),
      api.get<{ items: CheckinItem[] }>("/checkins?size=50").catch(() => null),
    ]).then(([ov, wk, bd, s, checkinRes]) => {
      setOverview(ov);
      setWeekly(wk);
      setBody(bd);
      if (s) setSettings(s);
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

  const weeklyWorkouts = weekly?.total_workouts ?? 0;
  const weeklyGoal = settings?.weekly_training_goal ?? 5;
  const goalPercent = Math.min(100, Math.round((weeklyWorkouts / weeklyGoal) * 100));

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
      label: "累计时长",
      value: formatDuration(overview?.total_duration_min ?? 0),
      icon: Clock,
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
                本周训练 {weeklyWorkouts} 次
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
              <div className="grid grid-cols-4 gap-2 sm:gap-4">
                {stats.map((stat) => (
                  <Card
                    key={stat.label}
                    className="group border-emerald-100 bg-white/80 shadow-sm backdrop-blur transition-all duration-200 hover:border-emerald-200 hover:shadow-md"
                  >
                    <CardContent className="flex items-center gap-1.5 p-2.5 sm:gap-3 sm:p-4">
                      <div className={cn("flex size-7 shrink-0 items-center justify-center rounded-xl transition-transform duration-200 group-hover:scale-110 sm:size-10", stat.bg)}>
                        <stat.icon className={cn("size-4 sm:size-5", stat.color)} />
                      </div>
                      <div className="min-w-0">
                        <p className="truncate text-[10px] text-emerald-600/60 sm:text-xs">{stat.label}</p>
                        <p className="truncate text-sm font-bold tabular-nums text-emerald-950 sm:text-lg">{stat.value}</p>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* 数据卡行：今日训练 / 本周目标 / 身体数据，移动端 3 列 */}
              <div className="grid grid-cols-3 gap-2 sm:gap-4 lg:gap-5">
                <TodayTraining checkin={todayCheckin} />
                <WeeklyGoalCard
                  weekly={weekly}
                  goalPercent={goalPercent}
                  goal={weeklyGoal}
                  onGoalChange={(g) =>
                    setSettings((s) =>
                      s ? { ...s, weekly_training_goal: g } : s
                    )
                  }
                />
                <BodyStatsCard body={body} longestStreak={overview?.longest_streak ?? 0} />
              </div>

              {/* 图表卡行：训练量 / 心情趋势，移动端全宽 */}
              <div className="grid grid-cols-1 gap-3 sm:gap-4 md:grid-cols-2 lg:gap-5">
                <WeeklyVolumeCard />
                <MoodTrendCard checkins={checkins} />
              </div>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
