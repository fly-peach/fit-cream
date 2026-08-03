import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  DumbbellIcon,
  FlameIcon,
  HeartPulseIcon,
  TrophyIcon,
  EyeIcon,
  EyeOffIcon,
  SmartphoneIcon,
  KeyRoundIcon,
  ArrowLeftIcon,
  ZapIcon,
  ShieldCheckIcon,
} from "lucide-react";
import { Logo } from "@/components/logo";

// 使用同源相对路径：dev 由 vite proxy 转发，prod 由后端同域托管，避免跨域
const API_URL = "/api";

type Mode = "sms" | "password" | "register" | "reset";

const CODE_LENGTH = 4;

/** 验证码对应的后端 code_type */
const CODE_TYPE: Record<Exclude<Mode, "password">, string> = {
  sms: "login",
  register: "register",
  reset: "reset_password",
};

const QUOTES = [
  "把汗水，变成答案。",
  "自律，即自由。",
  "今天的你，比昨天更强。",
  "科学健身，循序渐进。",
];

/** 登录/注册返回的用户 + Token 数据 */
interface AuthData {
  tokens?: { access_token?: string };
  user?: { id: string; role: string; name?: string | null; phone?: string | null };
}

/**
 * 认证相关请求辅助：fetch + 信封校验，成功返回 data，失败抛出带后端文案的 Error。
 *
 * 刻意不复用 lib/api.ts 的共享 client —— 那里把 40103（凭证无效）当作登录过期
 * 自动登出，会把"手机号或密码错误"误显示为"登录已过期"。
 */
async function authFetch<T = unknown>(path: string, body: unknown): Promise<T> {
  let json: { code?: number; message?: string; data?: T };
  try {
    const res = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    json = await res.json();
  } catch {
    throw new Error("网络错误，请检查后端服务是否启动");
  }
  if (json.code !== 200 && json.code !== 0) {
    throw new Error(json.message || "操作失败");
  }
  return json.data as T;
}

/* ------------------------------ 验证码分格输入 ------------------------------ */
function CodeInput({
  value,
  onChange,
  disabled,
  length = CODE_LENGTH,
}: {
  value: string;
  onChange: (v: string) => void;
  disabled?: boolean;
  length?: number;
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  const chars = Array.from({ length }, (_, i) => value[i] ?? "");

  const handleChange = (i: number, raw: string) => {
    const digits = raw.replace(/\D/g, "");
    if (!digits) return;
    const next = (value.slice(0, i) + digits + value.slice(i + digits.length)).slice(0, length);
    onChange(next);
    refs.current[Math.min(i + digits.length, length - 1)]?.focus();
  };

  const handleKeyDown = (i: number, e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      e.preventDefault();
      if (chars[i]) {
        onChange(value.slice(0, i) + value.slice(i + 1));
      } else if (i > 0) {
        onChange(value.slice(0, i - 1) + value.slice(i));
        refs.current[i - 1]?.focus();
      }
    } else if (e.key === "ArrowLeft" && i > 0) {
      refs.current[i - 1]?.focus();
    } else if (e.key === "ArrowRight" && i < length - 1) {
      refs.current[i + 1]?.focus();
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const digits = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, length);
    if (!digits) return;
    onChange(digits);
    refs.current[Math.min(digits.length, length - 1)]?.focus();
  };

  return (
    <div className="flex justify-between gap-2">
      {chars.map((c, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          type="text"
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          aria-label={`验证码第 ${i + 1} 位`}
          value={c}
          disabled={disabled}
          onChange={(e) => handleChange(i, e.target.value)}
          onKeyDown={(e) => handleKeyDown(i, e)}
          onPaste={handlePaste}
          onFocus={(e) => e.target.select()}
          className="size-12 rounded-xl border border-emerald-200 bg-emerald-50/50 text-center font-display text-xl font-bold text-emerald-950 tabular-nums outline-none transition-all duration-150 placeholder:text-transparent focus:border-emerald-500 focus:bg-white focus:ring-4 focus:ring-emerald-500/15 disabled:opacity-50 data-[filled=true]:border-emerald-300 data-[filled=true]:bg-white"
          data-filled={c !== ""}
        />
      ))}
    </div>
  );
}

/* ------------------------------ 左侧品牌面板 ------------------------------ */
function BrandPanel() {
  const [quoteIdx, setQuoteIdx] = useState(0);

  useEffect(() => {
    const t = setInterval(() => setQuoteIdx((i) => (i + 1) % QUOTES.length), 4000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="relative hidden overflow-hidden bg-emerald-950 lg:flex lg:w-[46%] xl:w-1/2">
      {/* 分层背景：光晕 + 网格 */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-40 -left-40 size-[32rem] rounded-full bg-emerald-500/25 blur-3xl" />
        <div className="absolute right-0 bottom-0 size-[28rem] translate-x-1/3 translate-y-1/3 rounded-full bg-teal-400/20 blur-3xl" />
        <div className="absolute top-1/2 left-1/3 size-72 rounded-full bg-green-400/10 blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.05]"
          style={{
            backgroundImage:
              "linear-gradient(to right, #34d399 1px, transparent 1px), linear-gradient(to bottom, #34d399 1px, transparent 1px)",
            backgroundSize: "48px 48px",
          }}
        />
      </div>

      {/* 浮动图标 */}
      <div className="pointer-events-none absolute top-[12%] right-[14%] float-slow">
        <DumbbellIcon className="size-9 text-emerald-400/40" />
      </div>
      <div className="pointer-events-none absolute top-[38%] right-[8%] float-slow [animation-delay:1.2s]">
        <FlameIcon className="size-7 text-orange-400/35" />
      </div>
      <div className="pointer-events-none absolute bottom-[24%] right-[20%] float-slow [animation-delay:2s]">
        <TrophyIcon className="size-8 text-amber-400/35" />
      </div>

      <div className="relative z-10 flex w-full flex-col justify-between p-12 xl:p-16">
        {/* 品牌 */}
        <div className="flex items-center gap-3">
          <Logo className="size-11 rounded-xl shadow-lg shadow-emerald-500/40" />
          <span className="font-display text-2xl font-bold tracking-tight text-white">
            Fit<span className="text-emerald-400">Cream</span>
          </span>
        </div>

        {/* 主文案 + 心率环 */}
        <div className="space-y-10">
          <div className="relative inline-block">
            {/* 心率扩散环 */}
            <div className="absolute -top-14 -right-16 size-24">
              <span className="pulse-ring absolute inset-0 rounded-full border-2 border-emerald-400/50" />
              <span className="pulse-ring absolute inset-0 rounded-full border-2 border-emerald-400/30 [animation-delay:0.8s]" />
              <span className="pulse-ring absolute inset-0 rounded-full border-2 border-emerald-400/20 [animation-delay:1.6s]" />
              <HeartPulseIcon className="absolute inset-0 m-auto size-9 text-emerald-400" />
            </div>
            <h1 className="font-display text-5xl leading-[1.15] font-bold tracking-tight text-white xl:text-6xl">
              把汗水，
              <br />
              变成<span className="text-emerald-400">答案</span>。
            </h1>
          </div>

          {/* 心电图 */}
          <svg
            viewBox="0 0 640 80"
            className="w-full max-w-md text-emerald-400/80"
            fill="none"
            aria-hidden
          >
            <path
              d="M0 40 H180 L200 40 L212 12 L226 66 L240 30 L252 40 H320 L338 40 L350 8 L366 72 L382 26 L394 40 H640"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="ecg-line"
            />
            <path
              d="M0 40 H180 L200 40 L212 12 L226 66 L240 30 L252 40 H320 L338 40 L350 8 L366 72 L382 26 L394 40 H640"
              stroke="currentColor"
              strokeWidth="1"
              strokeLinecap="round"
              className="opacity-20"
            />
          </svg>

          {/* 轮换口号 */}
          <div className="relative h-8">
            <AnimatePresence mode="wait">
              <motion.p
                key={quoteIdx}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.4 }}
                className="text-lg font-medium text-emerald-200/80"
              >
                {QUOTES[quoteIdx]}
              </motion.p>
            </AnimatePresence>
          </div>
        </div>

        {/* 特性标签 */}
        <div className="flex flex-wrap gap-3">
          {[
            { icon: ZapIcon, label: "AI 实时指导" },
            { icon: HeartPulseIcon, label: "科学定制计划" },
            { icon: ShieldCheckIcon, label: "数据安全守护" },
          ].map(({ icon: Icon, label }) => (
            <span
              key={label}
              className="flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-200 backdrop-blur-sm transition-colors hover:border-emerald-400/50 hover:bg-emerald-400/20"
            >
              <Icon className="size-4 text-emerald-400" />
              {label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}

/* -------------------------------- 登录页 -------------------------------- */
export default function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const logoutReason = useAuthStore((s) => s.logoutReason);
  const clearLogoutReason = useAuthStore((s) => s.clearLogoutReason);

  const [mode, setMode] = useState<Mode>("sms");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [countdown, setCountdown] = useState(0);
  const [sendingCode, setSendingCode] = useState(false);

  // 被动登出（token 失效等）跳转至此：直接以 logoutReason 作为提示来源，
  // 用户开始操作（提交 / 切换模式）时清除，避免在 effect 内 setState。
  const errorMessage = error || logoutReason;

  useEffect(() => {
    if (countdown <= 0) return;
    const t = setTimeout(() => setCountdown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown]);

  const isLoginMode = mode === "sms" || mode === "password";
  const needsCode = mode !== "password";

  const switchMode = (next: Mode) => {
    setMode(next);
    // 清空验证码与密码，避免跨模式残留（如重置码被带进验证码登录导致误导报错）
    setCode("");
    setPassword("");
    setError("");
    setNotice("");
    clearLogoutReason();
  };

  /** 完成登录态写入并跳转 */
  const finishAuth = (data: AuthData | null | undefined) => {
    const accessToken = data?.tokens?.access_token;
    const user = data?.user;
    if (accessToken && user) {
      setAuth(accessToken, {
        id: String(user.id),
        role: user.role === "admin" ? "admin" : "user",
        name: user.name,
        phone: user.phone,
      });
      navigate(user.role === "admin" ? "/admin/knowledge-bases" : "/knowledge-bases");
    } else {
      setError("未获取到 Token");
    }
  };

  /** 发送短信验证码 */
  const handleSendCode = async () => {
    setError("");
    setNotice("");
    if (phone.length !== 11) {
      setError("请先输入 11 位手机号");
      return;
    }
    setSendingCode(true);
    try {
      // 重置密码走专用端点：后端会先校验手机号已注册，避免给未注册号码白发短信
      if (mode === "reset") {
        await authFetch("/auth/request-password-reset", { phone });
      } else {
        await authFetch("/auth/send-verification-code", {
          phone,
          code_type: CODE_TYPE[mode as Exclude<Mode, "password">],
        });
      }
      setCountdown(60);
      setNotice("验证码已发送，请注意查收短信");
    } catch (e) {
      setError(e instanceof Error ? e.message : "发送失败");
    } finally {
      setSendingCode(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setNotice("");
    clearLogoutReason();

    if (needsCode && code.length !== CODE_LENGTH) {
      setError(`请输入 ${CODE_LENGTH} 位验证码`);
      return;
    }

    setLoading(true);
    try {
      if (mode === "sms") {
        finishAuth(await authFetch<AuthData>("/auth/sms-login", { phone, code }));
      } else if (mode === "password") {
        finishAuth(await authFetch<AuthData>("/auth/login", { phone, password }));
      } else if (mode === "register") {
        finishAuth(
          await authFetch<AuthData>("/auth/register", {
            phone,
            password,
            name: name || `用户${phone.slice(-4)}`,
            verification_code: code,
          })
        );
      } else {
        // reset：成功后清空并回到密码登录（switchMode 会重置 code/password）
        await authFetch("/auth/reset-password", { phone, code, new_password: password });
        switchMode("password");
        setNotice("密码重置成功，请使用新密码登录");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "操作失败");
    } finally {
      setLoading(false);
    }
  };

  const title =
    mode === "register" ? "创建账号" : mode === "reset" ? "重置密码" : "欢迎回来";
  const subtitle =
    mode === "register"
      ? "开启你的科学健身之旅"
      : mode === "reset"
        ? "验证手机号后设置新密码"
        : "登录你的 FitCream 账号";

  const inputCls =
    "h-12 rounded-xl border-emerald-200 bg-emerald-50/50 text-emerald-950 transition-all placeholder:text-emerald-400 focus-visible:border-emerald-400 focus-visible:bg-white focus-visible:ring-emerald-500/20";

  return (
    <div className="flex min-h-screen bg-gradient-to-br from-emerald-50 via-teal-50 to-green-100">
      <BrandPanel />

      {/* 右侧表单区 */}
      <div className="relative flex flex-1 items-center justify-center overflow-hidden px-4 py-10">
        {/* 右侧背景装饰 */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute -top-24 -right-24 size-80 rounded-full bg-emerald-200/40 blur-3xl" />
          <div className="absolute -bottom-24 -left-16 size-72 rounded-full bg-teal-200/40 blur-3xl" />
          <div
            className="absolute inset-0 opacity-[0.03]"
            style={{
              backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23059669' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
            }}
          />
        </div>

        <div className="relative w-full max-w-md">
          {/* 移动端品牌头 */}
          <div className="mb-8 flex flex-col items-center gap-3 lg:hidden">
            <Logo className="size-14 rounded-2xl shadow-lg shadow-emerald-500/30" />
            <h1 className="font-display text-2xl font-bold tracking-tight text-emerald-950">
              Fit<span className="text-emerald-600">Cream</span>
            </h1>
          </div>

          <div className="rounded-3xl border border-emerald-100/80 bg-white/85 p-8 shadow-xl shadow-emerald-900/5 backdrop-blur-sm">
            {/* 标题 */}
            <div className="mb-6">
              <AnimatePresence mode="wait">
                <motion.div
                  key={title}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -8 }}
                  transition={{ duration: 0.25 }}
                >
                  <h2 className="font-display text-2xl font-bold tracking-tight text-emerald-950">
                    {title}
                  </h2>
                  <p className="mt-1 text-sm font-medium text-emerald-700/60">{subtitle}</p>
                </motion.div>
              </AnimatePresence>
            </div>

            {/* 登录方式切换（仅登录态显示） */}
            {isLoginMode && (
              <div className="mb-6 grid grid-cols-2 gap-1 rounded-xl bg-emerald-100/60 p-1">
                {(
                  [
                    { key: "sms", label: "验证码登录", icon: SmartphoneIcon },
                    { key: "password", label: "密码登录", icon: KeyRoundIcon },
                  ] as const
                ).map(({ key, label, icon: Icon }) => (
                  <button
                    key={key}
                    type="button"
                    onClick={() => switchMode(key)}
                    className={`relative flex items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${
                      mode === key ? "text-emerald-800" : "text-emerald-600/60 hover:text-emerald-700"
                    }`}
                  >
                    {mode === key && (
                      <motion.span
                        layoutId="login-tab"
                        className="absolute inset-0 rounded-lg bg-white shadow-sm"
                        transition={{ type: "spring", stiffness: 400, damping: 32 }}
                      />
                    )}
                    <Icon className="relative z-10 size-4" />
                    <span className="relative z-10">{label}</span>
                  </button>
                ))}
              </div>
            )}

            {/* 返回登录（注册/重置时） */}
            {!isLoginMode && (
              <button
                type="button"
                onClick={() => switchMode("sms")}
                className="mb-5 flex items-center gap-1.5 text-sm font-semibold text-emerald-600 transition-colors hover:text-emerald-500"
              >
                <ArrowLeftIcon className="size-4" />
                返回登录
              </button>
            )}

            <form onSubmit={handleSubmit} className="space-y-5">
              {mode === "register" && (
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-emerald-900">昵称</label>
                  <Input
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    placeholder="怎么称呼你？"
                    className={inputCls}
                  />
                </div>
              )}

              <div className="space-y-2">
                <label className="text-sm font-semibold text-emerald-900">手机号</label>
                <Input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                  placeholder="请输入 11 位手机号"
                  required
                  pattern="[0-9]{11}"
                  maxLength={11}
                  className={inputCls}
                />
              </div>

              {needsCode && (
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <label className="text-sm font-semibold text-emerald-900">短信验证码</label>
                    <button
                      type="button"
                      onClick={handleSendCode}
                      disabled={countdown > 0 || sendingCode || phone.length !== 11}
                      className="text-sm font-semibold text-emerald-600 transition-colors hover:text-emerald-500 disabled:cursor-not-allowed disabled:text-emerald-400/60"
                    >
                      {sendingCode
                        ? "发送中…"
                        : countdown > 0
                          ? `${countdown}s 后重发`
                          : "获取验证码"}
                    </button>
                  </div>
                  <CodeInput value={code} onChange={setCode} disabled={loading} />
                </div>
              )}

              {(mode === "password" || mode === "register" || mode === "reset") && (
                <div className="space-y-2">
                  <label className="text-sm font-semibold text-emerald-900">
                    {mode === "reset" ? "新密码" : "密码"}
                  </label>
                  <div className="relative">
                    <Input
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="至少 6 位密码"
                      required
                      minLength={6}
                      className={`${inputCls} pr-10`}
                    />
                    <button
                      type="button"
                      className="absolute top-1/2 right-3 -translate-y-1/2 text-emerald-400 transition-colors hover:text-emerald-600"
                      onClick={() => setShowPassword(!showPassword)}
                      tabIndex={-1}
                      aria-label={showPassword ? "隐藏密码" : "显示密码"}
                    >
                      {showPassword ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
                    </button>
                  </div>
                </div>
              )}

              {notice && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">
                  {notice}
                </div>
              )}

              {errorMessage && (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-600">
                  {errorMessage}
                </div>
              )}

              <Button
                type="submit"
                disabled={loading}
                className="h-12 w-full rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-sm font-semibold text-white shadow-lg shadow-emerald-600/25 transition-all hover:from-emerald-500 hover:to-teal-500 hover:shadow-emerald-500/30 active:scale-[0.98] disabled:opacity-60"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="size-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                    处理中...
                  </span>
                ) : mode === "register" ? (
                  "创建账号"
                ) : mode === "reset" ? (
                  "重置密码"
                ) : (
                  "登录"
                )}
              </Button>
            </form>

            {/* 底部链接 */}
            <div className="mt-6 flex items-center justify-between text-sm">
              {isLoginMode ? (
                <>
                  <button
                    type="button"
                    className="font-semibold text-emerald-600 transition-colors hover:text-emerald-500 hover:underline"
                    onClick={() => switchMode("register")}
                  >
                    注册新账号
                  </button>
                  <button
                    type="button"
                    className="font-medium text-emerald-700/60 transition-colors hover:text-emerald-600"
                    onClick={() => switchMode("reset")}
                  >
                    忘记密码？
                  </button>
                </>
              ) : (
                <span className="w-full text-center text-emerald-800/60">
                  {mode === "register" ? "已有账号？" : "想起密码了？"}
                  <button
                    type="button"
                    className="ml-1 font-semibold text-emerald-600 transition-colors hover:text-emerald-500 hover:underline"
                    onClick={() => switchMode("sms")}
                  >
                    去登录
                  </button>
                </span>
              )}
            </div>
          </div>

          {/* 底部标语 */}
          <p className="mt-6 text-center text-xs font-medium tracking-wide text-emerald-700/50">
            科学健身 · 智能定制 · 持之以恒
          </p>
        </div>
      </div>
    </div>
  );
}
