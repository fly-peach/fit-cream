import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
  UsersIcon,
  DumbbellIcon,
  BookOpenIcon,
  MessageSquareIcon,
  Loader2,
  UserPlusIcon,
  ActivityIcon,
  ClipboardListIcon,
  FileTextIcon,
  ZapIcon,
  MessagesSquareIcon,
  TrendingUpIcon,
  UserCheckIcon,
  FlameIcon,
  LayersIcon,
  ClockIcon,
} from "lucide-react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { adminApi, type AdminOverviewStats, type AdminTrends } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

function StatCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  hint?: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-emerald-50/50 px-3.5 py-3">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600">
        {icon}
      </div>
      <div className="min-w-0">
        <p className="truncate text-xs text-emerald-600/60">{label}</p>
        <p className="text-xl font-bold tabular-nums text-emerald-950">
          {value}
          {hint && (
            <span className="ml-1 text-xs font-medium text-emerald-500/70">{hint}</span>
          )}
        </p>
      </div>
    </div>
  );
}

function KpiGroup({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <Card className="border-emerald-100 bg-white/80">
      <CardContent className="space-y-2.5 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-emerald-950">
          {icon}
          {title}
        </p>
        {children}
      </CardContent>
    </Card>
  );
}

function TrendChart({
  title,
  data,
  dataKey,
  color,
  formatter,
}: {
  title: string;
  data: { day: string; value: number }[];
  dataKey: string;
  color: string;
  formatter?: (v: number) => string;
}) {
  return (
    <Card className="border-emerald-100 bg-white/80">
      <CardContent className="space-y-2 p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-emerald-950">
          <TrendingUpIcon className="size-4 text-emerald-500" />
          {title}
        </p>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -18 }}>
              <defs>
                <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={color} stopOpacity={0.25} />
                  <stop offset="100%" stopColor={color} stopOpacity={0.02} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                dataKey="day"
                tick={{ fontSize: 10, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
                interval={Math.max(0, Math.ceil(data.length / 8) - 1)}
              />
              <YAxis
                tick={{ fontSize: 10, fill: "#94a3b8" }}
                tickLine={false}
                axisLine={false}
                allowDecimals={false}
              />
              <Tooltip
                formatter={(value) =>
                  formatter ? formatter(Number(value)) : String(value)
                }
                labelFormatter={(label) => `${label}`}
                contentStyle={{
                  borderRadius: 12,
                  border: "1px solid #d1fae5",
                  fontSize: 12,
                }}
              />
              <Area
                type="monotone"
                dataKey="value"
                stroke={color}
                strokeWidth={2}
                fill={`url(#grad-${dataKey})`}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}

export default function AdminOverviewPage() {
  const [stats, setStats] = useState<AdminOverviewStats | null>(null);
  const [trends, setTrends] = useState<AdminTrends | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([adminApi.getOverview(), adminApi.getTrends(30)]);
      setStats(s);
      setTrends(t);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载统计失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const series = useMemo(() => {
    if (!trends) return null;
    const toRows = (key: keyof AdminTrends) =>
      trends.days.map((d, i) => ({
        day: format(parseISO(d), "MM-dd", { locale: zhCN }),
        value: (trends[key] as number[])[i] ?? 0,
      }));
    return {
      registrations: toRows("registrations"),
      checkins: toRows("checkins"),
      conversations: toRows("conversations"),
      activeUsers: toRows("active_users"),
    };
  }, [trends]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-6 p-6">
        <header className="flex items-center justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-emerald-950">总览</h1>
            <p className="text-sm text-emerald-600/60">
              用户 · 训练 · 知识库 · 对话 四维度运营数据
            </p>
          </div>
          <Link
            to="/admin/users"
            className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-500"
          >
            查看用户列表
          </Link>
        </header>

        {error && (
          <div className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
            <span>{error}</span>
            <button onClick={() => setError("")} className="text-red-400">
              ✕
            </button>
          </div>
        )}

        {loading || !stats ? (
          <div className="flex items-center justify-center py-24 text-emerald-500">
            <Loader2 className="size-6 animate-spin" />
          </div>
        ) : (
          <>
            {/* ============ KPI 四维度 ============ */}
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <KpiGroup icon={<UsersIcon className="size-4 text-emerald-500" />} title="用户">
                <StatCard
                  icon={<UsersIcon className="size-4" />}
                  label="总用户数"
                  value={stats.users.total}
                />
                <StatCard
                  icon={<UserPlusIcon className="size-4" />}
                  label="近 7 天新增"
                  value={stats.users.new_7d}
                />
                <StatCard
                  icon={<UserCheckIcon className="size-4" />}
                  label="近 7 天活跃"
                  value={stats.users.active_7d}
                />
              </KpiGroup>

              <KpiGroup icon={<DumbbellIcon className="size-4 text-emerald-500" />} title="训练">
                <StatCard
                  icon={<FlameIcon className="size-4" />}
                  label="打卡总数"
                  value={stats.training.total_checkins}
                />
                <StatCard
                  icon={<ActivityIcon className="size-4" />}
                  label="近 30 天打卡"
                  value={stats.training.checkins_30d}
                />
                <StatCard
                  icon={<ClipboardListIcon className="size-4" />}
                  label="训练计划"
                  value={stats.training.active_plans}
                  hint={`/ ${stats.training.total_plans}`}
                />
              </KpiGroup>

              <KpiGroup icon={<BookOpenIcon className="size-4 text-emerald-500" />} title="知识库">
                <StatCard
                  icon={<LayersIcon className="size-4" />}
                  label="知识库数"
                  value={stats.kb.total_kbs}
                />
                <StatCard
                  icon={<FileTextIcon className="size-4" />}
                  label="文档数"
                  value={stats.kb.total_documents}
                />
                <StatCard
                  icon={<ZapIcon className="size-4" />}
                  label="待索引文档"
                  value={stats.kb.pending_documents}
                />
              </KpiGroup>

              <KpiGroup icon={<MessageSquareIcon className="size-4 text-emerald-500" />} title="对话">
                <StatCard
                  icon={<MessagesSquareIcon className="size-4" />}
                  label="会话数"
                  value={stats.conversation.total_threads}
                />
                <StatCard
                  icon={<ClockIcon className="size-4" />}
                  label="消息总数"
                  value={stats.conversation.total_messages}
                />
                <StatCard
                  icon={<UserCheckIcon className="size-4" />}
                  label="近 7 天会话"
                  value={stats.conversation.threads_7d}
                />
              </KpiGroup>
            </div>

            {/* ============ 近 30 天趋势图 ============ */}
            <div className={cn("grid gap-4 xl:grid-cols-2")}>
              {series && (
                <>
                  <TrendChart
                    title="近 30 天注册趋势"
                    data={series.registrations}
                    dataKey="registrations"
                    color="#10b981"
                  />
                  <TrendChart
                    title="近 30 天打卡趋势"
                    data={series.checkins}
                    dataKey="checkins"
                    color="#0ea5e9"
                  />
                  <TrendChart
                    title="近 30 天对话趋势（消息数）"
                    data={series.conversations}
                    dataKey="conversations"
                    color="#8b5cf6"
                  />
                  <TrendChart
                    title="近 30 天活跃用户趋势"
                    data={series.activeUsers}
                    dataKey="active_users"
                    color="#f59e0b"
                  />
                </>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
