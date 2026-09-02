import { useCallback, useEffect, useState } from "react";
import { format, parseISO } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
  Loader2,
  RefreshCw,
  WalletIcon,
  BanknoteIcon,
  GiftIcon,
  TrendingUpIcon,
  CheckCircle2Icon,
  XCircleIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  adminApi,
  type BillingOverview,
  type BillingPricing,
  type RechargeApplication,
} from "@/lib/admin-api";
import { showError, showSuccess } from "@/lib/toast";

const PAGE_SIZE = 20;

function fmtTime(iso: string): string {
  try {
    return format(parseISO(iso), "MM-dd HH:mm", { locale: zhCN });
  } catch {
    return iso;
  }
}

function AppStatusBadge({ status }: { status: string }) {
  if (status === "confirmed")
    return <Badge className="bg-emerald-100 text-emerald-700">已到账</Badge>;
  if (status === "rejected")
    return <Badge className="bg-rose-100 text-rose-600">已拒绝</Badge>;
  return <Badge className="bg-amber-100 text-amber-700">待核销</Badge>;
}

export default function AdminBillingPage() {
  const [overview, setOverview] = useState<BillingOverview | null>(null);
  const [apps, setApps] = useState<RechargeApplication[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState<
    "all" | "pending" | "confirmed" | "rejected"
  >("pending");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);

  // 单价编辑
  const [pricing, setPricing] = useState<BillingPricing | null>(null);
  const [savingPricing, setSavingPricing] = useState(false);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadApps = useCallback(async () => {
    try {
      setLoading(true);
      const data = await adminApi.listRechargeApplications({
        status: statusFilter === "all" ? undefined : statusFilter,
        page,
        size: PAGE_SIZE,
      });
      setApps(data.items);
      setTotal(data.total);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  const loadAll = useCallback(async () => {
    try {
      const [ov, pr] = await Promise.all([
        adminApi.getBillingOverview().catch(() => null),
        adminApi.getBillingPricing().catch(() => null),
      ]);
      setOverview(ov);
      setPricing(pr);
    } catch (e) {
      showError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    void loadApps();
  }, [loadApps]);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  const review = async (id: string, approve: boolean) => {
    setBusyId(id);
    try {
      await adminApi.reviewRechargeApplication(id, approve);
      showSuccess(approve ? "已确认到账" : "已拒绝该申请");
      await loadApps();
      await loadAll();
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setBusyId(null);
    }
  };

  const savePricing = async () => {
    if (!pricing) return;
    setSavingPricing(true);
    try {
      await adminApi.updateBillingPricing(pricing);
      showSuccess("计费单价已更新");
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setSavingPricing(false);
    }
  };

  const setPrice = (key: keyof BillingPricing, val: string) => {
    const num = Number(val);
    if (!Number.isFinite(num)) return;
    setPricing((prev) => (prev ? { ...prev, [key]: num } : prev));
  };

  return (
    <div className="h-full overflow-auto p-4 md:p-6">
      <div className="mx-auto max-w-5xl space-y-5">
        {/* ===== 概览 ===== */}
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Card className="border-emerald-100">
            <CardContent className="flex items-center gap-3 p-4">
              <WalletIcon className="size-6 text-emerald-500" />
              <div>
                <p className="text-xs text-emerald-600/60">累计充值</p>
                <p className="text-lg font-bold text-emerald-950 tabular-nums">
                  ¥{Number(overview?.recharged ?? 0).toFixed(2)}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-emerald-100">
            <CardContent className="flex items-center gap-3 p-4">
              <BanknoteIcon className="size-6 text-emerald-500" />
              <div>
                <p className="text-xs text-emerald-600/60">累计消费</p>
                <p className="text-lg font-bold text-emerald-950 tabular-nums">
                  ¥{Number(overview?.consumed ?? 0).toFixed(2)}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-emerald-100">
            <CardContent className="flex items-center gap-3 p-4">
              <GiftIcon className="size-6 text-emerald-500" />
              <div>
                <p className="text-xs text-emerald-600/60">累计赠送</p>
                <p className="text-lg font-bold text-emerald-950 tabular-nums">
                  ¥{Number(overview?.granted ?? 0).toFixed(2)}
                </p>
              </div>
            </CardContent>
          </Card>
          <Card className="border-emerald-100">
            <CardContent className="flex items-center gap-3 p-4">
              <TrendingUpIcon className="size-6 text-amber-500" />
              <div>
                <p className="text-xs text-emerald-600/60">成本估算</p>
                <p className="text-lg font-bold text-amber-600 tabular-nums">
                  ¥{Number(overview?.estimated_cost ?? 0).toFixed(2)}
                </p>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* ===== 充值申请核销 ===== */}
        <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <CardTitle className="text-base font-semibold text-emerald-950">
                充值申请核销
                {Number(overview?.pending_applications ?? 0) > 0 && (
                  <Badge className="ml-2 bg-amber-100 text-amber-700">
                    {overview?.pending_applications} 待处理
                  </Badge>
                )}
              </CardTitle>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-emerald-600"
                onClick={() => {
                  void loadApps();
                  void loadAll();
                }}
              >
                <RefreshCw className="size-4" />
              </Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-emerald-600/50">
              当前为自动到账模式：用户提交充值申请即到账（转账备注=用户 ID），
              无需人工核销；此页用于查看充值记录与核对转账。
            </p>
            <div className="flex gap-2">
              {(["pending", "confirmed", "rejected", "all"] as const).map((s) => (
                <Button
                  key={s}
                  variant={statusFilter === s ? "default" : "outline"}
                  size="sm"
                  className={statusFilter === s ? "bg-emerald-600" : "text-emerald-700"}
                  onClick={() => {
                    setPage(1);
                    setStatusFilter(s);
                  }}
                >
                  {s === "all"
                    ? "全部"
                    : s === "pending"
                    ? "待核销"
                    : s === "confirmed"
                    ? "已到账"
                    : "已拒绝"}
                </Button>
              ))}
            </div>

            {loading ? (
              <div className="flex items-center gap-2 py-8 text-sm text-emerald-600/60">
                <Loader2 className="size-4 animate-spin" /> 加载中...
              </div>
            ) : apps.length === 0 ? (
              <p className="py-8 text-center text-sm text-emerald-600/50">
                暂无充值申请
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-emerald-100 text-left text-xs text-emerald-600/60">
                      <th className="px-3 py-2">单号</th>
                      <th className="px-3 py-2">金额</th>
                      <th className="px-3 py-2">方式</th>
                      <th className="px-3 py-2">备注</th>
                      <th className="px-3 py-2">状态</th>
                      <th className="px-3 py-2">时间</th>
                      <th className="px-3 py-2">操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {apps.map((a) => (
                      <tr
                        key={a.id}
                        className="border-b border-emerald-50 text-emerald-900"
                      >
                        <td className="px-3 py-2 font-mono text-xs">{a.app_no}</td>
                        <td className="px-3 py-2 font-semibold tabular-nums">
                          ¥{Number(a.amount).toFixed(2)}
                        </td>
                        <td className="px-3 py-2">
                          {a.method === "alipay" ? "支付宝" : "微信"}
                        </td>
                        <td className="max-w-[160px] truncate px-3 py-2 text-emerald-600/70">
                          {a.note ?? "-"}
                        </td>
                        <td className="px-3 py-2">
                          <AppStatusBadge status={a.status} />
                        </td>
                        <td className="px-3 py-2 text-emerald-600/60">
                          {fmtTime(a.created_at)}
                        </td>
                        <td className="px-3 py-2">
                          {a.status === "pending" ? (
                            <div className="flex gap-1.5">
                              <Button
                                size="sm"
                                className="bg-emerald-600 hover:bg-emerald-700"
                                disabled={busyId === a.id}
                                onClick={() => void review(a.id, true)}
                              >
                                {busyId === a.id ? (
                                  <Loader2 className="size-3.5 animate-spin" />
                                ) : (
                                  <CheckCircle2Icon className="size-3.5" />
                                )}
                                确认到账
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                className="text-rose-600"
                                disabled={busyId === a.id}
                                onClick={() => void review(a.id, false)}
                              >
                                <XCircleIcon className="size-3.5" />
                                拒绝
                              </Button>
                            </div>
                          ) : (
                            <span className="text-xs text-emerald-600/40">
                              {a.review_note ?? "-"}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {totalPages > 1 && (
              <div className="flex items-center justify-between text-sm text-emerald-600/60">
                <span>
                  第 {page} / {totalPages} 页（共 {total} 条）
                </span>
                <div className="flex gap-2">
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
                    onClick={() => setPage((p) => p + 1)}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ===== 单价配置 ===== */}
        <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
          <CardHeader>
            <CardTitle className="text-base font-semibold text-emerald-950">
              计费单价（元 / 百万 token）
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {pricing ? (
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <div>
                  <label className="text-xs text-emerald-700">对话输入</label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    value={pricing.input_price}
                    onChange={(e) => setPrice("input_price", e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-700">对话输出</label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    value={pricing.output_price}
                    onChange={(e) => setPrice("output_price", e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-700">缓存命中输入</label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    value={pricing.cache_read_price}
                    onChange={(e) => setPrice("cache_read_price", e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-700">Embedding</label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={pricing.embedding_price}
                    onChange={(e) => setPrice("embedding_price", e.target.value)}
                    className="mt-1"
                  />
                </div>
                <div>
                  <label className="text-xs text-emerald-700">Rerank</label>
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    value={pricing.rerank_price}
                    onChange={(e) => setPrice("rerank_price", e.target.value)}
                    className="mt-1"
                  />
                </div>
              </div>
            ) : (
              <p className="text-sm text-emerald-600/50">单价读取失败</p>
            )}
            <p className="text-xs text-emerald-600/50">
              对话：输入 3、输出 10、缓存命中 0.3（成本约 0.8/2.7/0.1，元/百万
              token）。检索：embedding 0.5、rerank 0.6（text-embedding-v3 /
              qwen3-rerank 成本价，元/百万输入 token）。更新后立即对后续消费生效。
            </p>
            <Button
              className="bg-emerald-600 hover:bg-emerald-700"
              disabled={savingPricing || !pricing}
              onClick={() => void savePricing()}
            >
              {savingPricing ? <Loader2 className="size-4 animate-spin" /> : null}
              保存单价
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
