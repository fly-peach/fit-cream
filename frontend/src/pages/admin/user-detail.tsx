import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
  ArrowLeftIcon,
  UserIcon,
  Loader2,
  ClipboardListIcon,
  FlameIcon,
  UtensilsIcon,
  ScaleIcon,
  ClockIcon,
  GlobeIcon,
  CalendarIcon,
  WalletIcon,
  GiftIcon,
} from "lucide-react";
import { buttonVariants } from "@/components/ui/button";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { adminApi, type AdminCheckin, type AdminUserDetail, type BillingAccount } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { showError, showSuccess } from "@/lib/toast";

const goalLabels: Record<string, string> = {
  lose_fat: "减脂",
  gain_muscle: "增肌",
  maintain: "维持",
  improve_health: "改善健康",
};

function SummaryStat({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl bg-emerald-50/50 px-3.5 py-3">
      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-emerald-600">
        {icon}
      </div>
      <div>
        <p className="text-xs text-emerald-600/60">{label}</p>
        <p className="text-xl font-bold tabular-nums text-emerald-950">{value}</p>
      </div>
    </div>
  );
}

export default function AdminUserDetailPage() {
  const { userId = "" } = useParams();
  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [checkins, setCheckins] = useState<AdminCheckin[]>([]);
  const [billing, setBilling] = useState<BillingAccount | null>(null);
  const [grantAmount, setGrantAmount] = useState("10");
  const [grantBusy, setGrantBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      const [u, c, b] = await Promise.all([
        adminApi.getUser(userId),
        adminApi.listUserCheckins(userId, 10),
        adminApi.getUserBilling(userId).catch(() => null),
      ]);
      setUser(u);
      setCheckins(c);
      setBilling(b);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    load();
  }, [load]);

  const grant = async () => {
    const amt = Number(grantAmount);
    if (!amt || amt <= 0) {
      showError("请输入有效的加量金额");
      return;
    }
    setGrantBusy(true);
    try {
      const b = await adminApi.grantUserBilling(userId, amt, "管理员手动加量");
      setBilling(b);
      showSuccess(`已加量 ${amt} 元`);
    } catch (e) {
      showError(e instanceof Error ? e.message : "加量失败");
    } finally {
      setGrantBusy(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-emerald-500">
        <Loader2 className="size-6 animate-spin" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-4 p-6">
        <p className="text-sm text-red-600">{error || "用户不存在"}</p>
        <Link
          to="/admin/users"
          className={cn(buttonVariants({ variant: "outline", size: "sm" }))}
        >
          <ArrowLeftIcon className="size-4" />
          返回用户列表
        </Link>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div className="flex items-center gap-3">
          <Link
            to="/admin/users"
            className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "size-9")}
          >
            <ArrowLeftIcon className="size-4" />
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-bold text-emerald-950">
              {user.name || user.phone || user.id}
            </h1>
            <p className="text-sm text-emerald-600/60">
              {user.phone || "无手机号"}
            </p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {user.role === "admin" ? (
              <Badge className="bg-amber-100 text-amber-700">管理员</Badge>
            ) : (
              <Badge variant="secondary">用户</Badge>
            )}
            {user.is_active ? (
              <Badge className="bg-emerald-100 text-emerald-700">正常</Badge>
            ) : (
              <Badge className="bg-red-100 text-red-600">已禁用</Badge>
            )}
          </div>
        </div>

        {error && (
          <div className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
            <span>{error}</span>
            <button onClick={() => setError("")} className="text-red-400">
              ✕
            </button>
          </div>
        )}

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <SummaryStat
            icon={<ClipboardListIcon className="size-4" />}
            label="训练计划"
            value={user.plan_count}
          />
          <SummaryStat
            icon={<FlameIcon className="size-4" />}
            label="打卡次数"
            value={user.checkin_count}
          />
          <SummaryStat
            icon={<UtensilsIcon className="size-4" />}
            label="饮食计划"
            value={user.diet_plan_count}
          />
          <SummaryStat
            icon={<ScaleIcon className="size-4" />}
            label="最新体重"
            value={
              user.latest_health_metric?.weight_kg != null
                ? `${user.latest_health_metric.weight_kg} kg`
                : "—"
            }
          />
        </div>

        {/* 余额与加量 */}
        <Card className="border-emerald-100 bg-white/80">
          <CardContent className="space-y-3 p-5">
            <p className="flex items-center gap-2 text-sm font-semibold text-emerald-950">
              <WalletIcon className="size-4 text-emerald-500" />
              余额
              {billing?.status === "frozen" && (
                <Badge className="bg-rose-100 text-rose-600">已冻结</Badge>
              )}
            </p>
            <div className="grid grid-cols-4 gap-3 text-center">
              <div className="rounded-xl bg-emerald-50/60 py-3">
                <p className="text-xs text-emerald-600/60">余额</p>
                <p className="text-lg font-bold text-emerald-950 tabular-nums">
                  ¥{Number(billing?.balance ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="rounded-xl bg-emerald-50/60 py-3">
                <p className="text-xs text-emerald-600/60">累计充值</p>
                <p className="text-lg font-bold text-emerald-950 tabular-nums">
                  ¥{Number(billing?.total_recharged ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="rounded-xl bg-emerald-50/60 py-3">
                <p className="text-xs text-emerald-600/60">累计赠送</p>
                <p className="text-lg font-bold text-emerald-950 tabular-nums">
                  ¥{Number(billing?.total_granted ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="rounded-xl bg-emerald-50/60 py-3">
                <p className="text-xs text-emerald-600/60">累计消费</p>
                <p className="text-lg font-bold text-emerald-950 tabular-nums">
                  ¥{Number(billing?.total_consumed ?? 0).toFixed(2)}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <GiftIcon className="size-4 text-emerald-500" />
              <span className="text-xs text-emerald-600/60">给该用户加量（赠送余额）</span>
              <Input
                type="number"
                min={1}
                step="1"
                value={grantAmount}
                onChange={(e) => setGrantAmount(e.target.value)}
                className="w-28"
              />
              <Button
                size="sm"
                className="bg-emerald-600 hover:bg-emerald-700"
                disabled={grantBusy}
                onClick={() => void grant()}
              >
                {grantBusy ? <Loader2 className="size-4 animate-spin" /> : <GiftIcon className="size-4" />}
                加量
              </Button>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-2">
          {/* 基本资料 */}
          <Card className="border-emerald-100 bg-white/80">
            <CardContent className="space-y-3 p-5">
              <p className="flex items-center gap-2 text-sm font-semibold text-emerald-950">
                <UserIcon className="size-4 text-emerald-500" />
                基本资料
              </p>
              <dl className="space-y-2 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-emerald-600/60">账号 ID</dt>
                  <dd className="truncate font-mono text-xs text-emerald-900">{user.id}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-emerald-600/60">性别</dt>
                  <dd className="text-emerald-900">{user.gender || "—"}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-emerald-600/60">手机号验证</dt>
                  <dd className="text-emerald-900">{user.is_verified ? "已验证" : "未验证"}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-emerald-600/60">最近登录</dt>
                  <dd className="text-emerald-900">
                    {user.last_login_at
                      ? format(parseISO(user.last_login_at), "yyyy-MM-dd HH:mm", {
                          locale: zhCN,
                        })
                      : "—"}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="flex items-center gap-1 text-emerald-600/60">
                    <GlobeIcon className="size-3.5" />
                    上次登录 IP
                  </dt>
                  <dd className="font-mono text-xs text-emerald-900">
                    {user.last_login_ip || "—"}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="flex items-center gap-1 text-emerald-600/60">
                    <CalendarIcon className="size-3.5" />
                    注册时间
                  </dt>
                  <dd className="text-emerald-900">
                    {format(parseISO(user.created_at), "yyyy-MM-dd HH:mm", {
                      locale: zhCN,
                    })}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-emerald-600/60">Token 累计用量</dt>
                  <dd className="text-emerald-900">{user.total_tokens.toLocaleString()}</dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-emerald-600/60">Token 近 7 天</dt>
                  <dd className="text-emerald-900">{user.tokens_7d.toLocaleString()}</dd>
                </div>
              </dl>

              {user.settings && (
                <div className="rounded-lg bg-emerald-50/50 px-3 py-2.5 text-sm">
                  <p className="mb-1.5 text-xs font-medium text-emerald-600/60">健身设置</p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-emerald-900">
                    <span>目标：{goalLabels[user.settings.goal ?? ""] ?? user.settings.goal ?? "—"}</span>
                    {user.settings.weekly_training_goal != null && (
                      <span>每周训练：{user.settings.weekly_training_goal} 次</span>
                    )}
                    {user.settings.calorie_goal != null && (
                      <span>卡路里目标：{user.settings.calorie_goal} kcal</span>
                    )}
                  </div>
                </div>
              )}

              {user.latest_health_metric && (
                <div className="rounded-lg bg-emerald-50/50 px-3 py-2.5 text-sm">
                  <p className="mb-1.5 text-xs font-medium text-emerald-600/60">
                    最新健康指标
                    {user.latest_health_metric.measure_date
                      ? `（${user.latest_health_metric.measure_date}）`
                      : ""}
                  </p>
                  <div className="flex flex-wrap gap-x-4 gap-y-1 text-emerald-900">
                    {user.latest_health_metric.weight_kg != null && (
                      <span>体重：{user.latest_health_metric.weight_kg} kg</span>
                    )}
                    {user.latest_health_metric.body_fat_pct != null && (
                      <span>体脂：{user.latest_health_metric.body_fat_pct}%</span>
                    )}
                    {user.latest_health_metric.bmi != null && (
                      <span>BMI：{user.latest_health_metric.bmi}</span>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* 近期打卡 */}
          <Card className="border-emerald-100 bg-white/80">
            <CardContent className="space-y-3 p-5">
              <p className="flex items-center gap-2 text-sm font-semibold text-emerald-950">
                <FlameIcon className="size-4 text-emerald-500" />
                近期打卡
                <span className="ml-auto text-xs font-normal text-emerald-600/60">
                  最近 {checkins.length} 条
                </span>
              </p>
              {checkins.length === 0 ? (
                <p className="py-10 text-center text-sm text-emerald-600/50">暂无打卡记录</p>
              ) : (
                <div className="space-y-2">
                  {checkins.map((c) => (
                    <div
                      key={c.id}
                      className="flex items-center gap-3 rounded-lg bg-emerald-50/50 px-3 py-2.5"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-emerald-950">{c.date}</p>
                        {c.note && (
                          <p className="line-clamp-1 text-xs text-emerald-600/60">{c.note}</p>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-3 text-xs text-emerald-700">
                        {c.duration_min != null && (
                          <span className="flex items-center gap-1 tabular-nums">
                            <ClockIcon className="size-3.5" />
                            {c.duration_min} 分
                          </span>
                        )}
                        {c.calories_burned != null && (
                          <span className="tabular-nums">{c.calories_burned} kcal</span>
                        )}
                        {c.mood != null && <span>心情 {c.mood}/5</span>}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
