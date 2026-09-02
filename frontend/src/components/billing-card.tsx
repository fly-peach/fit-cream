import { useCallback, useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ChevronDown,
  ChevronUp,
  Copy,
  Loader2,
  Wallet,
} from "lucide-react";
import { api } from "@/lib/api";
import { showError, showSuccess } from "@/lib/toast";

interface BillingMe {
  user_id: string;
  balance: number;
  total_recharged: number;
  total_granted: number;
  total_consumed: number;
  status: string;
  pricing: {
    input_price: number;
    output_price: number;
    cache_read_price: number;
  } | null;
  qr_code_url: string;
}

interface BillingTx {
  id: string;
  type: string;
  amount: number;
  balance_after: number;
  source: string;
  description: string | null;
  billed: boolean;
  created_at: string;
}

interface RechargeApp {
  id: string;
  app_no: string;
  amount: number;
  method: string;
  note: string | null;
  status: string;
  created_at: string;
}

const sourceLabels: Record<string, string> = {
  chat: "AI 对话",
  memory_extraction: "记忆提取",
  memory_consolidation: "记忆整合",
  recharge: "充值",
  admin_grant: "管理员赠送",
  coupon: "注册礼包",
};

const txnTypeLabels: Record<string, string> = {
  recharge: "充值",
  consume: "消费",
  grant: "赠送",
  refund: "退款",
};

const statusLabels: Record<string, string> = {
  pending: "待核销",
  confirmed: "已到账",
  rejected: "已拒绝",
};

function fmt(v: number | null | undefined): string {
  return (Number(v ?? 0) || 0).toFixed(2);
}

function fmtTime(iso: string): string {
  try {
    const d = new Date(iso);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
      d.getDate()
    ).padStart(2, "0")} ${String(d.getHours()).padStart(2, "0")}:${String(
      d.getMinutes()
    ).padStart(2, "0")}`;
  } catch {
    return iso;
  }
}

export function BillingCard() {
  const [open, setOpen] = useState(false);
  const [billing, setBilling] = useState<BillingMe | null>(null);
  const [txs, setTxs] = useState<BillingTx[]>([]);
  const [apps, setApps] = useState<RechargeApp[]>([]);
  const [loading, setLoading] = useState(true);

  // 充值申请表单
  const [rechargeOpen, setRechargeOpen] = useState(false);
  const [amount, setAmount] = useState("30");
  const [method, setMethod] = useState("wechat");
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [lastApp, setLastApp] = useState<RechargeApp | null>(null);
  // 订单模式（虎皮椒）：二维码地址 + 轮询中的订单 id
  const [orderQr, setOrderQr] = useState("");
  const [orderId, setOrderId] = useState<string | null>(null);
  // 备用模式（未配置支付网关）：提交即到账，需按备注用户 ID 转账
  const [fallbackMode, setFallbackMode] = useState(false);

  const refresh = useCallback(() => {
    setLoading(true);
    Promise.all([
      api.get<BillingMe>("/billing/me").catch(() => null),
      api
        .get<{ items: BillingTx[] }>("/billing/transactions?page=1&size=20")
        .catch(() => null),
      api
        .get<RechargeApp[]>("/billing/recharge-applications")
        .catch(() => null),
    ])
      .then(([b, t, a]) => {
        setBilling(b);
        setTxs(t?.items ?? []);
        setApps(a ?? []);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const submitRecharge = async () => {
    const amt = Number(amount);
    if (!amt || amt <= 0) {
      showError("请输入有效的充值金额");
      return;
    }
    setSubmitting(true);
    try {
      const data = await api.post<{
        app: RechargeApp;
        qr_code_url: string;
        pay_url: string;
      }>("/billing/recharge-applications", {
        amount: amt,
        method,
        note: note || undefined,
      });
      setLastApp(data.app);
      setOrderQr(data.qr_code_url);
      setFallbackMode(!data.qr_code_url);
      setNote("");
      refresh();
      if (data.qr_code_url) {
        // 订单模式：启动轮询等待支付结果
        setOrderId(data.app.id);
      }
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  // 订单模式轮询：付款成功后自动到账并刷新余额
  useEffect(() => {
    if (!orderId) return;
    const timer = setInterval(async () => {
      try {
        const apps = await api.get<RechargeApp[]>("/billing/recharge-applications");
        const cur = apps.find((a) => a.id === orderId);
        if (!cur) return;
        if (cur.status === "confirmed") {
          setOrderId(null);
          setOrderQr("");
          setLastApp(cur);
          showSuccess("充值已到账");
          refresh();
        } else if (cur.status === "rejected") {
          setOrderId(null);
          setOrderQr("");
          showError("充值失败，请联系管理员");
        }
      } catch {
        // 轮询失败忽略，下次再试
      }
    }, 3000);
    return () => clearInterval(timer);
  }, [orderId, refresh]);

  const copyText = (text: string, label: string) => {
    try {
      void navigator.clipboard.writeText(text);
      showSuccess(`${label}已复制`);
    } catch {
      // ignore
    }
  };

  return (
    <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Wallet className="size-4 text-emerald-600" />
            <CardTitle className="text-base font-semibold text-emerald-950">
              我的余额
            </CardTitle>
          </div>
          <div className="flex items-center gap-1.5">
            <Button
              variant="outline"
              size="sm"
              className="text-emerald-700"
              onClick={() => {
                setRechargeOpen(true);
                setLastApp(null);
                setOrderQr("");
                setOrderId(null);
                setFallbackMode(false);
              }}
            >
              充值
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 text-emerald-600/70"
              onClick={() => setOpen((v) => !v)}
              title={open ? "收起" : "展开"}
            >
              {open ? <ChevronUp className="size-4" /> : <ChevronDown className="size-4" />}
            </Button>
          </div>
        </div>
      </CardHeader>

      {loading && !billing ? (
        <CardContent className="flex items-center gap-2 text-sm text-emerald-600/60">
          <Loader2 className="size-4 animate-spin" /> 加载中...
        </CardContent>
      ) : (
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="rounded-xl bg-emerald-50/60 py-3">
              <p className="text-xs text-emerald-600/60">余额（元）</p>
              <p className="text-xl font-bold text-emerald-950 tabular-nums">
                {fmt(billing?.balance)}
              </p>
            </div>
            <div className="rounded-xl bg-emerald-50/60 py-3">
              <p className="text-xs text-emerald-600/60">累计消费</p>
              <p className="text-xl font-bold text-emerald-950 tabular-nums">
                {fmt(billing?.total_consumed)}
              </p>
            </div>
            <div className="rounded-xl bg-emerald-50/60 py-3">
              <p className="text-xs text-emerald-600/60">累计充值</p>
              <p className="text-xl font-bold text-emerald-950 tabular-nums">
                {fmt(billing?.total_recharged)}
              </p>
            </div>
          </div>

          {billing?.pricing && (
            <p className="text-xs leading-relaxed text-emerald-600/60">
              计费单价（元/百万 token）：输入 {billing.pricing.input_price}、
              输出 {billing.pricing.output_price}、
              缓存命中输入 {billing.pricing.cache_read_price}。AI 对话按实际用量计费。
            </p>
          )}

          {open && (
            <div className="space-y-4">
              {txs.length > 0 && (
                <div className="space-y-1.5 text-sm">
                  <p className="text-xs font-semibold text-emerald-700">最近流水</p>
                  {txs.slice(0, 8).map((t) => (
                    <div
                      key={t.id}
                      className="flex items-center justify-between rounded-lg bg-emerald-50/40 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-emerald-800">
                          {txnTypeLabels[t.type] ?? t.type}
                          {t.description ? ` · ${t.description}` : ""}
                        </p>
                        <p className="text-xs text-emerald-600/50">
                          {fmtTime(t.created_at)}
                          {t.source ? ` · ${sourceLabels[t.source] ?? t.source}` : ""}
                        </p>
                      </div>
                      <span
                        className={`shrink-0 tabular-nums font-medium ${
                          Number(t.amount) >= 0 ? "text-emerald-600" : "text-rose-500"
                        }`}
                      >
                        {Number(t.amount) >= 0 ? "+" : ""}
                        {fmt(t.amount)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {apps.length > 0 && (
                <div className="space-y-1.5 text-sm">
                  <p className="text-xs font-semibold text-emerald-700">充值申请</p>
                  {apps.slice(0, 5).map((a) => (
                    <div
                      key={a.id}
                      className="flex items-center justify-between rounded-lg bg-emerald-50/40 px-3 py-2"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-emerald-800">
                          单号 {a.app_no}
                          {a.method === "alipay" ? "（支付宝）" : "（微信）"}
                        </p>
                        <p className="text-xs text-emerald-600/50">{fmtTime(a.created_at)}</p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="text-emerald-900 tabular-nums">{fmt(a.amount)}</span>
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs ${
                            a.status === "confirmed"
                              ? "bg-emerald-100 text-emerald-700"
                              : a.status === "rejected"
                              ? "bg-rose-100 text-rose-600"
                              : "bg-amber-100 text-amber-700"
                          }`}
                        >
                          {statusLabels[a.status] ?? a.status}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      )}

      {/* 充值弹窗（虎皮椒订单机制 / 备用收款码流程） */}
      <Dialog open={rechargeOpen} onOpenChange={setRechargeOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle className="text-emerald-950">充值</DialogTitle>
            <DialogDescription className="text-emerald-700/60">
              {orderQr
                ? "请扫码支付，付款成功后自动到账"
                : "充值到账后即可继续使用 AI 对话"}
            </DialogDescription>
          </DialogHeader>

          {/* 订单模式：等待扫码支付 */}
          {orderQr ? (
            <div className="space-y-3">
              <div className="flex flex-col items-center gap-2">
                <img
                  src={orderQr}
                  alt="支付二维码"
                  className="h-48 w-48 rounded-xl border border-emerald-100 object-contain"
                />
                <p className="flex items-center gap-1.5 text-xs text-emerald-600/60">
                  <Loader2 className="size-3.5 animate-spin" /> 等待支付结果...
                </p>
              </div>
              <p className="rounded-lg bg-emerald-50 px-3 py-2 text-center text-xs text-emerald-700">
                订单号 {lastApp?.app_no}
              </p>
            </div>
          ) : lastApp && lastApp.status === "confirmed" ? (
            /* 已到账 */
            <div className="space-y-2 rounded-xl bg-emerald-50 p-3 text-sm">
              <p className="font-medium text-emerald-800">
                已到账 ¥{fmt(lastApp.amount)}！
              </p>
              {fallbackMode ? (
                <p className="text-emerald-700/70">
                  请用转账备注
                  <button
                    type="button"
                    className="mx-1 inline-flex items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.5 font-mono text-emerald-800"
                    onClick={() => copyText(billing?.user_id ?? "", "备注")}
                    title="点击复制用户 ID"
                  >
                    {billing?.user_id ?? "-"}
                    <Copy className="size-3" />
                  </button>
                  付款到下方收款码，我们将按备注核账。
                </p>
              ) : (
                <p className="text-emerald-700/70">支付成功，额度已自动到账。</p>
              )}
            </div>
          ) : lastApp && lastApp.status !== "confirmed" ? (
            /* 待核销（备用审核模式） */
            <div className="space-y-2 rounded-xl bg-amber-50 p-3 text-sm">
              <p className="font-medium text-amber-800">
                请转账并备注单号：{lastApp.app_no}
              </p>
              <Button
                variant="outline"
                size="sm"
                className="text-amber-700"
                onClick={() => copyText(lastApp.app_no, "单号")}
              >
                <Copy className="size-3.5" /> 复制单号
              </Button>
              <p className="text-xs text-amber-600/70">
                已提交待核销申请，到账后可在「充值申请」中查看状态
              </p>
            </div>
          ) : null}

          {/* 备用收款码（仅非订单模式时展示） */}
          {!orderQr && (
            billing?.qr_code_url ? (
              <div className="flex flex-col items-center gap-2">
                <img
                  src={billing.qr_code_url}
                  alt="收款码"
                  className="h-44 w-44 rounded-xl border border-emerald-100 object-contain"
                />
                <p className="text-xs text-emerald-600/50">保存图片后用微信/支付宝扫码</p>
              </div>
            ) : (
              <p className="rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-600/60">
                收款码暂未配置，请联系管理员充值
              </p>
            )
          )}

          {/* 充值表单（未下单时显示） */}
          {!orderQr && !(lastApp && lastApp.status === "confirmed") && (
            <div className="space-y-3">
              <div>
                <label className="text-xs text-emerald-700">充值金额（元）</label>
                <Input
                  type="number"
                  min={1}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="30"
                  className="mt-1"
                />
              </div>
              <div>
                <label className="text-xs text-emerald-700">支付方式</label>
                <Select value={method} onValueChange={setMethod}>
                  <SelectTrigger className="mt-1">
                    <SelectValue placeholder="选择支付方式" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="wechat">微信支付</SelectItem>
                    <SelectItem value="alipay">支付宝</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="text-xs text-emerald-700">备注（可选）</label>
                <Input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="填写支付凭证说明，便于对账"
                  className="mt-1"
                />
              </div>
            </div>
          )}

          <DialogFooter>
            {!orderQr && (
              <Button
                className="w-full bg-emerald-600 hover:bg-emerald-700"
                disabled={submitting}
                onClick={() => void submitRecharge()}
              >
                {submitting ? <Loader2 className="size-4 animate-spin" /> : null}
                {lastApp && lastApp.status === "confirmed" ? "继续充值" : "提交订单"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
