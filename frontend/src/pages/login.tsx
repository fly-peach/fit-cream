import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DumbbellIcon, FlameIcon, HeartPulseIcon, TrophyIcon, EyeIcon, EyeOffIcon } from "lucide-react";

// 使用同源相对路径：dev 由 vite proxy 转发，prod 由后端同域托管，避免跨域
const API_URL = "/api";

export default function LoginPage() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const logoutReason = useAuthStore((s) => s.logoutReason);
  const clearLogoutReason = useAuthStore((s) => s.clearLogoutReason);

  const [mode, setMode] = useState<"login" | "register">("login");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  // 被动登出（token 失效等）跳转至此：直接以 logoutReason 作为提示来源，
  // 用户开始操作（提交 / 切换模式）时清除，避免在 effect 内 setState。
  const errorMessage = error || logoutReason;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    clearLogoutReason();
    setLoading(true);

    try {
      const endpoint = mode === "login" ? "/auth/login" : "/auth/register";
      const body =
        mode === "login"
          ? { phone, password }
          : { phone, password, name: name || `用户${phone.slice(-4)}` };

      const res = await fetch(`${API_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const json = await res.json();

      if (json.code !== 200 && json.code !== 0) {
        setError(json.message || "操作失败");
        return;
      }

      const accessToken = json.data?.tokens?.access_token;
      const user = json.data?.user;
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
    } catch {
      setError("网络错误，请检查后端服务是否启动");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-gradient-to-br from-emerald-50 via-teal-50 to-green-100 px-4">
      {/* 装饰性背景元素 */}
      <div className="pointer-events-none absolute inset-0">
        {/* 光晕圆 */}
        <div className="absolute -top-32 -left-32 size-96 rounded-full bg-emerald-200/40 blur-3xl" />
        <div className="absolute -right-24 -bottom-24 size-80 rounded-full bg-teal-200/50 blur-3xl" />
        <div className="absolute top-1/3 right-1/4 size-48 rounded-full bg-green-200/30 blur-2xl" />

        {/* 浮动图标装饰 */}
        <div className="absolute top-[15%] left-[12%] animate-bounce [animation-duration:3s]">
          <DumbbellIcon className="size-8 text-emerald-300/60" />
        </div>
        <div className="absolute top-[25%] right-[15%] animate-bounce [animation-delay:0.5s] [animation-duration:4s]">
          <FlameIcon className="size-7 text-orange-300/50" />
        </div>
        <div className="absolute bottom-[20%] left-[18%] animate-bounce [animation-delay:1s] [animation-duration:3.5s]">
          <HeartPulseIcon className="size-7 text-rose-300/50" />
        </div>
        <div className="absolute right-[20%] bottom-[28%] animate-bounce [animation-delay:1.5s] [animation-duration:4.5s]">
          <TrophyIcon className="size-8 text-amber-300/50" />
        </div>

        {/* 网格纹理 */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23059669' fill-opacity='1'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />
      </div>

      {/* 登录卡片 */}
      <div className="relative w-full max-w-md">
        <div className="rounded-2xl border border-emerald-100/80 bg-white/80 p-8 shadow-xl shadow-emerald-900/5 backdrop-blur-sm">
          {/* Logo */}
          <div className="mb-8 flex flex-col items-center gap-4">
            <div className="flex size-16 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/30">
              <DumbbellIcon className="size-8 text-white" />
            </div>
            <div className="text-center">
              <h1 className="text-3xl font-bold tracking-tight text-emerald-950">
                Fit<span className="text-emerald-600">Cream</span>
              </h1>
              <p className="mt-1.5 text-sm font-medium text-emerald-700/70">
                你的 AI 私人健身教练
              </p>
            </div>
          </div>

          {/* 表单 */}
          <form onSubmit={handleSubmit} className="space-y-5">
            {mode === "register" && (
              <div className="space-y-2">
                <label className="text-sm font-semibold text-emerald-900">
                  昵称
                </label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="怎么称呼你？"
                  className="h-11 rounded-xl border-emerald-200 bg-emerald-50/50 text-emerald-950 transition-all placeholder:text-emerald-400 focus-visible:border-emerald-400 focus-visible:bg-white focus-visible:ring-emerald-500/20"
                />
              </div>
            )}

            <div className="space-y-2">
              <label className="text-sm font-semibold text-emerald-900">
                手机号
              </label>
              <Input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value.replace(/\D/g, ""))}
                placeholder="请输入 11 位手机号"
                required
                pattern="[0-9]{11}"
                maxLength={11}
                className="h-11 rounded-xl border-emerald-200 bg-emerald-50/50 text-emerald-950 transition-all placeholder:text-emerald-400 focus-visible:border-emerald-400 focus-visible:bg-white focus-visible:ring-emerald-500/20"
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold text-emerald-900">
                密码
              </label>
              <div className="relative">
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="至少 6 位密码"
                  required
                  minLength={6}
                  className="h-11 rounded-xl border-emerald-200 bg-emerald-50/50 pr-10 text-emerald-950 transition-all placeholder:text-emerald-400 focus-visible:border-emerald-400 focus-visible:bg-white focus-visible:ring-emerald-500/20"
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-emerald-400 transition-colors hover:text-emerald-600"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
                </button>
              </div>
            </div>

            {errorMessage && (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-600">
                {errorMessage}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="h-11 w-full rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-sm font-semibold text-white shadow-lg shadow-emerald-600/25 transition-all hover:from-emerald-500 hover:to-teal-500 hover:shadow-emerald-500/30 active:scale-[0.98] disabled:opacity-60"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="size-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  处理中...
                </span>
              ) : mode === "login" ? (
                "登录"
              ) : (
                "创建账号"
              )}
            </Button>
          </form>

          {/* 切换登录/注册 */}
          <p className="mt-6 text-center text-sm text-emerald-800/60">
            {mode === "login" ? "还没有账号？" : "已有账号？"}
            <button
              type="button"
              className="ml-1 font-semibold text-emerald-600 transition-colors hover:text-emerald-500 hover:underline"
              onClick={() => {
                setMode(mode === "login" ? "register" : "login");
                setError("");
                clearLogoutReason();
              }}
            >
              {mode === "login" ? "立即注册" : "去登录"}
            </button>
          </p>
        </div>

        {/* 底部标语 */}
        <p className="mt-6 text-center text-xs font-medium tracking-wide text-emerald-700/50">
          科学健身 · 智能定制 · 持之以恒
        </p>
      </div>
    </div>
  );
}