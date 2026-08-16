import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
  UsersIcon,
  Loader2,
  SearchIcon,
  BanIcon,
  CheckCircle2Icon,
  ArrowRightIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { adminApi, type AdminUserListItem } from "@/lib/admin-api";
import { ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { showError, showSuccess } from "@/lib/toast";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;

function RoleBadge({ role }: { role: string }) {
  return role === "admin" ? (
    <Badge className="bg-amber-100 text-amber-700">管理员</Badge>
  ) : (
    <Badge variant="secondary">用户</Badge>
  );
}

function StatusBadge({ active }: { active: boolean }) {
  return active ? (
    <Badge className="bg-emerald-100 text-emerald-700">正常</Badge>
  ) : (
    <Badge className="bg-red-100 text-red-600">已禁用</Badge>
  );
}

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

export default function AdminUsersPage() {
  const me = useAuthStore((s) => s.user);
  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [keyword, setKeyword] = useState("");
  const [role, setRole] = useState<"all" | "user" | "admin">("all");
  const [status, setStatus] = useState<"all" | "active" | "disabled">("all");

  const [busyId, setBusyId] = useState<string | null>(null);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await adminApi.listUsers({
        page,
        size: PAGE_SIZE,
        keyword: keyword.trim() || undefined,
        role: role === "all" ? undefined : role,
        is_active:
          status === "all" ? undefined : status === "active" ? true : false,
      });
      setUsers(data.items);
      setTotal(data.total);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [page, keyword, role, status]);

  useEffect(() => {
    load();
  }, [load]);

  const toggleActive = async (u: AdminUserListItem) => {
    const target = !u.is_active;
    if (!target && !window.confirm(`确定禁用用户「${u.name || u.phone || u.id}」吗？`)) {
      return;
    }
    setBusyId(u.id);
    try {
      await adminApi.updateUser(u.id, { is_active: target });
      showSuccess(target ? "已启用" : "已禁用");
      await load();
    } catch (e) {
      showError(e instanceof ApiError ? e.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  const toggleRole = async (u: AdminUserListItem) => {
    const target = u.role === "admin" ? "user" : "admin";
    if (target === "user" && !window.confirm(`确定取消用户「${u.name || u.phone || u.id}」的管理员权限吗？`)) {
      return;
    }
    setBusyId(u.id);
    try {
      await adminApi.updateUser(u.id, { role: target });
      showSuccess(target === "admin" ? "已设为管理员" : "已取消管理员");
      await load();
    } catch (e) {
      showError(e instanceof ApiError ? e.message : "操作失败");
    } finally {
      setBusyId(null);
    }
  };

  const isSelf = (u: AdminUserListItem) => u.id === me?.id;

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-6 p-6">
        <header className="flex items-center gap-3">
          <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-100">
            <UsersIcon className="size-5 text-emerald-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-emerald-950">用户管理</h1>
            <p className="text-sm text-emerald-600/60">
              搜索、筛选用户并管理账号状态与角色
            </p>
          </div>
        </header>

        {/* 搜索与筛选 */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-52 flex-1">
            <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-emerald-400" />
            <Input
              value={keyword}
              onChange={(e) => {
                setKeyword(e.target.value);
                setPage(1);
              }}
              placeholder="搜索手机号 / 姓名 / 邮箱"
              className="rounded-xl border-emerald-200 bg-white/70 pl-9"
            />
          </div>
          <Select
            value={role}
            onValueChange={(v) => {
              setRole(v as typeof role);
              setPage(1);
            }}
          >
            <SelectTrigger className="border-emerald-200 text-emerald-800">
              <SelectValue>
                {role === "all" ? "全部角色" : role === "admin" ? "管理员" : "普通用户"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部角色</SelectItem>
              <SelectItem value="admin">管理员</SelectItem>
              <SelectItem value="user">普通用户</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={status}
            onValueChange={(v) => {
              setStatus(v as typeof status);
              setPage(1);
            }}
          >
            <SelectTrigger className="border-emerald-200 text-emerald-800">
              <SelectValue>
                {status === "all"
                  ? "全部状态"
                  : status === "active"
                    ? "正常"
                    : "已禁用"}
              </SelectValue>
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="active">正常</SelectItem>
              <SelectItem value="disabled">已禁用</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {error && (
          <div className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
            <span>{error}</span>
            <button onClick={() => setError("")} className="text-red-400">
              ✕
            </button>
          </div>
        )}

        {/* 用户表格 */}
        <Card className="border-emerald-100 bg-white/80">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-left text-sm">
              <thead>
                <tr className="border-b border-emerald-100 text-xs text-emerald-600/60">
                  <th className="px-4 py-3 font-medium">用户</th>
                  <th className="px-4 py-3 font-medium">角色</th>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-4 py-3 font-medium">计划数</th>
                  <th className="px-4 py-3 font-medium">打卡数</th>
                  <th className="px-4 py-3 font-medium">Token 用量</th>
                  <th className="px-4 py-3 font-medium">最近登录</th>
                  <th className="px-4 py-3 font-medium">注册时间</th>
                  <th className="px-4 py-3 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-16 text-center text-emerald-500">
                      <Loader2 className="mx-auto size-5 animate-spin" />
                    </td>
                  </tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-16 text-center text-sm text-emerald-600/50">
                      暂无用户
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr
                      key={u.id}
                      className="border-b border-emerald-50 last:border-0 hover:bg-emerald-50/30"
                    >
                      <td className="px-4 py-3">
                        <p className="truncate font-medium text-emerald-950">
                          {u.name || "未设置姓名"}
                        </p>
                        <p className="truncate text-xs text-emerald-600/60">
                          {u.phone || u.id}
                        </p>
                      </td>
                      <td className="px-4 py-3">
                        <RoleBadge role={u.role} />
                      </td>
                      <td className="px-4 py-3">
                        <StatusBadge active={u.is_active} />
                      </td>
                      <td className="px-4 py-3 tabular-nums text-emerald-900">
                        {u.plan_count}
                      </td>
                      <td className="px-4 py-3 tabular-nums text-emerald-900">
                        {u.checkin_count}
                      </td>
                      <td className="px-4 py-3 tabular-nums text-emerald-900">
                        <span className="font-medium">{formatTokens(u.total_tokens)}</span>
                        <span className="ml-1 text-xs text-emerald-500/70">
                          /7d {formatTokens(u.tokens_7d)}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-xs text-emerald-600/70">
                        {u.last_login_at
                          ? format(parseISO(u.last_login_at), "yyyy-MM-dd HH:mm", {
                              locale: zhCN,
                            })
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-xs text-emerald-600/70">
                        {format(parseISO(u.created_at), "yyyy-MM-dd", {
                          locale: zhCN,
                        })}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <Link
                            to={`/admin/users/${u.id}`}
                            className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-100/60"
                          >
                            详情
                            <ArrowRightIcon className="size-3" />
                          </Link>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busyId === u.id || isSelf(u)}
                            onClick={() => toggleRole(u)}
                            className={cn(
                              "text-xs",
                              u.role === "admin"
                                ? "text-amber-600 hover:bg-amber-50"
                                : "text-emerald-700 hover:bg-emerald-50"
                            )}
                          >
                            {u.role === "admin" ? "取消管理员" : "设管理员"}
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            disabled={busyId === u.id || isSelf(u)}
                            onClick={() => toggleActive(u)}
                            className={cn(
                              "text-xs",
                              u.is_active
                                ? "text-red-600 hover:bg-red-50"
                                : "text-emerald-700 hover:bg-emerald-50"
                            )}
                          >
                            {u.is_active ? (
                              <>
                                <BanIcon className="size-3.5" />
                                禁用
                              </>
                            ) : (
                              <>
                                <CheckCircle2Icon className="size-3.5" />
                                启用
                              </>
                            )}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {/* 分页 */}
        {!loading && total > 0 && (
          <div className="flex items-center justify-between text-sm text-emerald-600/60">
            <span>
              共 {total} 位用户 · 第 {page} / {totalPages} 页
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                上一页
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                下一页
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
