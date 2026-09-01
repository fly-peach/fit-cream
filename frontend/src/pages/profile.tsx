import { useEffect, useState } from "react"
import { AppLayout } from "@/components/app-layout"
import { ApiKeyPanel } from "@/components/api-key-panel"
import { BillingCard } from "@/components/billing-card"
import { FitnessProfileCard } from "@/components/fitness-profile-card"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  KeyRound,
  Loader2,
  Save,
  Smartphone,
  Trash2,
  User,
} from "lucide-react"
import { api, ApiError } from "@/lib/api"
import { clearDsKey, getDsKey, getDsKeyExpiry, saveDsKey } from "@/lib/ds-key"
import { useAuthStore } from "@/stores/auth-store"
import { useCountdown } from "@/hooks/use-countdown"

interface UserProfile {
  id: string
  phone: string | null
  name: string | null
  height_cm: number | null
  weight_kg: number | null
  birth_date: string | null
  age: number | null
  gender: string | null
  goal: string | null
  created_at: string
}

interface TokenUsage {
  total_tokens: number
  input_tokens: number
  output_tokens: number
  llm_calls: number
  by_source: { source: string; total_tokens: number; llm_calls: number }[]
}

const genderOptions = [
  { value: "male", label: "男" },
  { value: "female", label: "女" },
  { value: "other", label: "其他" },
]

const goalOptions = [
  { value: "lose_fat", label: "减脂塑形" },
  { value: "gain_muscle", label: "增肌增重" },
  { value: "maintain", label: "保持健康" },
  { value: "improve_health", label: "改善体质" },
]

const sourceLabels: Record<string, string> = {
  chat: "对话",
  memory_extraction: "记忆提取",
  memory_consolidation: "记忆整合",
  embedding: "向量化",
}

/** 手机号脱敏：前 3 位 + **** + 后 4 位 */
function maskPhone(p: string | null | undefined): string {
  return p && p.length >= 7 ? `${p.slice(0, 3)}****${p.slice(-4)}` : (p ?? "")
}

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [form, setForm] = useState({
    name: "",
    height_cm: "",
    weight_kg: "",
    birth_date: "",
    gender: "",
    goal: "",
  })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState("")
  const [usage, setUsage] = useState<TokenUsage | null>(null)

  // DeepSeek 模型（BYOK）：key 仅存前端 localStorage（15 天 TTL）
  const [dsKeyInput, setDsKeyInput] = useState("")
  const [dsKeyPresent, setDsKeyPresent] = useState<boolean>(() => !!getDsKey())
  const [dsExpiry, setDsExpiry] = useState<number | null>(() =>
    getDsKeyExpiry()
  )
  const [dsVerifying, setDsVerifying] = useState(false)
  const [dsMsg, setDsMsg] = useState("")
  const [dsError, setDsError] = useState("")

  // 账号与安全 —— 换绑手机号（两步：验证旧号 → 绑定新号）
  const [changeStep, setChangeStep] = useState(0)
  const [oldCode, setOldCode] = useState("")
  const [newPhone, setNewPhone] = useState("")
  const [newCode, setNewCode] = useState("")
  const [sendingOld, setSendingOld] = useState(false)
  const [sendingNew, setSendingNew] = useState(false)
  const [changeSubmitting, setChangeSubmitting] = useState(false)
  const [changeMsg, setChangeMsg] = useState("")
  const [changeError, setChangeError] = useState("")
  const oldCountdown = useCountdown()
  const newCountdown = useCountdown()

  // 账号与安全 —— 注销（密码 + 短信验证码双因素）
  const [deactOpen, setDeactOpen] = useState(false)
  const [deactPassword, setDeactPassword] = useState("")
  const [deactCode, setDeactCode] = useState("")
  const [deactError, setDeactError] = useState("")
  const [sendingDeact, setSendingDeact] = useState(false)
  const [deactSubmitting, setDeactSubmitting] = useState(false)
  const deactCountdown = useCountdown()

  // 账号与安全 —— 折叠展开（默认收起）
  const [securityOpen, setSecurityOpen] = useState(false)
  // Token 用量 / DeepSeek —— 折叠展开（默认收起，压缩页面）
  const [usageOpen, setUsageOpen] = useState(false)
  const [dsOpen, setDsOpen] = useState(false)

  useEffect(() => {
    api
      .get<TokenUsage>("/users/me/token-usage?days=30")
      .then(setUsage)
      .catch(() => {})
  }, [])

  useEffect(() => {
    api
      .get<UserProfile>("/users/me")
      .then((data) => {
        setProfile(data)
        setForm({
          name: data.name ?? "",
          height_cm: data.height_cm?.toString() ?? "",
          weight_kg: data.weight_kg?.toString() ?? "",
          birth_date: data.birth_date ?? "",
          gender: data.gender ?? "",
          goal: data.goal ?? "",
        })
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const handleSave = async () => {
    setSaving(true)
    setError("")
    setSaved(false)
    try {
      const payload: Record<string, unknown> = {
        name: form.name || null,
        gender: form.gender || null,
        goal: form.goal || null,
      }
      if (form.height_cm) payload.height_cm = Number(form.height_cm)
      if (form.weight_kg) payload.weight_kg = Number(form.weight_kg)
      if (form.birth_date) payload.birth_date = form.birth_date

      const updated = await api.put<UserProfile>("/users/me", payload)
      setProfile(updated)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSaving(false)
    }
  }

  const handleSaveDsKey = async () => {
    const key = dsKeyInput.trim()
    if (key.length < 8) {
      setDsError("请输入有效的 DeepSeek API Key")
      setDsMsg("")
      return
    }
    setDsVerifying(true)
    setDsError("")
    setDsMsg("")
    try {
      // 先校验再落 localStorage：无效 key 不保存
      const data = await api.post<{ valid: boolean; error?: string }>(
        "/chat/verify-deepseek-key",
        { deepseek_api_key: key }
      )
      if (data.valid) {
        saveDsKey(key)
        setDsKeyInput("")
        setDsKeyPresent(true)
        setDsExpiry(getDsKeyExpiry())
        setDsMsg("保存成功：对话已切换为 DeepSeek 模型")
      } else {
        setDsError(
          data.error ? `校验失败：${data.error}` : "校验失败，请检查 key"
        )
      }
    } catch (e) {
      setDsError(e instanceof Error ? e.message : "校验失败，请稍后重试")
    } finally {
      setDsVerifying(false)
    }
  }

  const handleClearDsKey = () => {
    clearDsKey()
    setDsKeyPresent(false)
    setDsExpiry(null)
    setDsKeyInput("")
    setDsMsg("已清除，对话将使用默认模型")
    setDsError("")
  }

  const bmi =
    profile?.height_cm && profile?.weight_kg
      ? (profile.weight_kg / Math.pow(profile.height_cm / 100, 2)).toFixed(1)
      : null

  const sendOldCode = async () => {
    setChangeError("")
    setChangeMsg("")
    setSendingOld(true)
    try {
      await api.post("/auth/send-verification-code", {
        phone: profile?.phone,
        code_type: "change_phone_old",
      })
      oldCountdown.start(60)
      setChangeMsg("验证码已发送至当前手机号")
    } catch (e) {
      setChangeError(e instanceof Error ? e.message : "发送失败")
    } finally {
      setSendingOld(false)
    }
  }

  const sendNewCode = async () => {
    setChangeError("")
    setChangeMsg("")
    if (!/^\d{11}$/.test(newPhone)) {
      setChangeError("请输入 11 位新手机号")
      return
    }
    setSendingNew(true)
    try {
      await api.post("/auth/send-verification-code", {
        phone: newPhone,
        code_type: "change_phone_new",
      })
      newCountdown.start(60)
      setChangeMsg("验证码已发送至新手机号")
    } catch (e) {
      setChangeError(e instanceof Error ? e.message : "发送失败")
    } finally {
      setSendingNew(false)
    }
  }

  const submitChangePhone = async () => {
    setChangeError("")
    setChangeMsg("")
    if (!/^\d{11}$/.test(newPhone)) {
      setChangeError("请输入 11 位新手机号")
      return
    }
    setChangeSubmitting(true)
    try {
      await api.post("/auth/change-phone", {
        new_phone: newPhone,
        old_code: oldCode,
        new_code: newCode,
      })
      if (profile) setProfile({ ...profile, phone: newPhone })
      const st = useAuthStore.getState()
      if (st.user) st.setAuth({ ...st.user, phone: newPhone })
      setChangeStep(0)
      setOldCode("")
      setNewPhone("")
      setNewCode("")
      setChangeMsg("手机号更换成功")
    } catch (e) {
      setChangeError(e instanceof Error ? e.message : "换绑失败")
    } finally {
      setChangeSubmitting(false)
    }
  }

  const cancelChange = () => {
    setChangeStep(0)
    setOldCode("")
    setNewPhone("")
    setNewCode("")
    setChangeMsg("")
    setChangeError("")
  }

  const sendDeactCode = async () => {
    setDeactError("")
    setSendingDeact(true)
    try {
      await api.post("/auth/send-verification-code", {
        phone: profile?.phone,
        code_type: "deactivate",
      })
      deactCountdown.start(60)
    } catch (e) {
      setDeactError(e instanceof Error ? e.message : "发送失败")
    } finally {
      setSendingDeact(false)
    }
  }

  const submitDeactivate = async () => {
    setDeactError("")
    setDeactSubmitting(true)
    try {
      await api.post("/auth/deactivate", {
        password: deactPassword,
        verification_code: deactCode,
      })
      useAuthStore.getState().logout("账号已注销")
    } catch (e) {
      if (e instanceof ApiError && e.code === 40300) {
        setDeactError("管理员账号需由其他管理员处理")
      } else {
        setDeactError(e instanceof Error ? e.message : "注销失败")
      }
    } finally {
      setDeactSubmitting(false)
    }
  }

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-6 p-6">
          <header className="flex items-center gap-1.5 sm:gap-3">
            <div className="flex size-7 items-center justify-center rounded-xl bg-emerald-100 sm:size-11 sm:rounded-2xl">
              <User className="size-3 text-emerald-600 sm:size-5" />
            </div>
            <div>
              <h1 className="text-[12px] font-bold text-emerald-950 sm:text-xl">
                个人中心
              </h1>
              <p className="text-[8px] text-emerald-600/60 sm:text-sm">
                管理你的身体数据与健身目标
              </p>
            </div>
          </header>

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : (
            <>
              {bmi && (
                <Card className="border-emerald-100 bg-gradient-to-br from-emerald-50 to-teal-50/60">
                  <CardContent className="flex items-center justify-around p-6">
                    <div className="text-center">
                      <p className="text-xs text-emerald-600/60">身高</p>
                      <p className="text-2xl font-bold text-emerald-950">
                        {profile?.height_cm}
                        <span className="ml-1 text-sm font-normal">cm</span>
                      </p>
                    </div>
                    <div className="h-10 w-px bg-emerald-200" />
                    <div className="text-center">
                      <p className="text-xs text-emerald-600/60">体重</p>
                      <p className="text-2xl font-bold text-emerald-950">
                        {profile?.weight_kg}
                        <span className="ml-1 text-sm font-normal">kg</span>
                      </p>
                    </div>
                    <div className="h-10 w-px bg-emerald-200" />
                    <div className="text-center">
                      <p className="text-xs text-emerald-600/60">BMI</p>
                      <p className="text-2xl font-bold text-emerald-600">
                        {bmi}
                      </p>
                    </div>
                  </CardContent>
                </Card>
              )}

              <FitnessProfileCard
                basicTab={
                  <>
                    <div className="grid gap-2.5 sm:grid-cols-2">
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-emerald-800">
                          昵称
                        </label>
                        <Input
                          value={form.name}
                          onChange={(e) =>
                            setForm({ ...form, name: e.target.value })
                          }
                          placeholder="请输入昵称"
                          className="h-9 border-emerald-200 focus-visible:ring-emerald-400"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-emerald-800">
                          出生日期
                        </label>
                        <Input
                          type="date"
                          value={form.birth_date}
                          onChange={(e) =>
                            setForm({ ...form, birth_date: e.target.value })
                          }
                          className="h-9 border-emerald-200 focus-visible:ring-emerald-400"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-emerald-800">
                          身高 (cm)
                        </label>
                        <Input
                          type="number"
                          value={form.height_cm}
                          onChange={(e) =>
                            setForm({ ...form, height_cm: e.target.value })
                          }
                          placeholder="请输入身高"
                          className="h-9 border-emerald-200 focus-visible:ring-emerald-400"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-emerald-800">
                          体重 (kg)
                        </label>
                        <Input
                          type="number"
                          value={form.weight_kg}
                          onChange={(e) =>
                            setForm({ ...form, weight_kg: e.target.value })
                          }
                          placeholder="请输入体重"
                          className="h-9 border-emerald-200 focus-visible:ring-emerald-400"
                        />
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-emerald-800">
                          性别
                        </label>
                        <Select
                          value={form.gender}
                          onValueChange={(v) =>
                            setForm({ ...form, gender: v ?? "" })
                          }
                        >
                          <SelectTrigger className="h-9 border-emerald-200 focus:ring-emerald-400">
                            <SelectValue placeholder="请选择性别">
                              {
                                genderOptions.find(
                                  (o) => o.value === form.gender
                                )?.label
                              }
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent>
                            {genderOptions.map((o) => (
                              <SelectItem key={o.value} value={o.value}>
                                {o.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <label className="text-xs font-medium text-emerald-800">
                          健身目标
                        </label>
                        <Select
                          value={form.goal}
                          onValueChange={(v) =>
                            setForm({ ...form, goal: v ?? "" })
                          }
                        >
                          <SelectTrigger className="h-9 border-emerald-200 focus:ring-emerald-400">
                            <SelectValue placeholder="请选择目标">
                              {
                                goalOptions.find((o) => o.value === form.goal)
                                  ?.label
                              }
                            </SelectValue>
                          </SelectTrigger>
                          <SelectContent>
                            {goalOptions.map((o) => (
                              <SelectItem key={o.value} value={o.value}>
                                {o.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    {error && <p className="text-sm text-red-500">{error}</p>}

                    <div className="flex items-center gap-3 pt-2">
                      <Button
                        onClick={handleSave}
                        disabled={saving}
                        className="bg-emerald-600 text-white hover:bg-emerald-500"
                      >
                        {saving ? (
                          <Loader2 className="mr-2 size-4 animate-spin" />
                        ) : saved ? (
                          <CheckCircle2 className="mr-2 size-4" />
                        ) : (
                          <Save className="mr-2 size-4" />
                        )}
                        {saved ? "已保存" : "保存资料"}
                      </Button>
                    </div>
                  </>
                }
              />

              <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base font-semibold text-emerald-950">
                      Token 用量
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 text-emerald-600/70"
                      onClick={() => setUsageOpen((v) => !v)}
                      title={usageOpen ? "收起" : "展开"}
                    >
                      {usageOpen ? (
                        <ChevronUp className="size-4" />
                      ) : (
                        <ChevronDown className="size-4" />
                      )}
                    </Button>
                  </div>
                </CardHeader>
                {usageOpen && (
                  <CardContent className="space-y-4">
                    {usage ? (
                      <>
                        <div className="grid grid-cols-3 gap-3 text-center">
                          <div className="rounded-xl bg-emerald-50/60 py-3">
                            <p className="text-xs text-emerald-600/60">累计</p>
                            <p className="text-xl font-bold text-emerald-950 tabular-nums">
                              {usage.total_tokens.toLocaleString()}
                            </p>
                          </div>
                          <div className="rounded-xl bg-emerald-50/60 py-3">
                            <p className="text-xs text-emerald-600/60">输入</p>
                            <p className="text-xl font-bold text-emerald-950 tabular-nums">
                              {usage.input_tokens.toLocaleString()}
                            </p>
                          </div>
                          <div className="rounded-xl bg-emerald-50/60 py-3">
                            <p className="text-xs text-emerald-600/60">输出</p>
                            <p className="text-xl font-bold text-emerald-950 tabular-nums">
                              {usage.output_tokens.toLocaleString()}
                            </p>
                          </div>
                        </div>
                        {usage.by_source.length > 0 && (
                          <div className="space-y-1.5 text-sm">
                            {usage.by_source.map((s) => (
                              <div
                                key={s.source}
                                className="flex items-center justify-between rounded-lg bg-emerald-50/40 px-3 py-2"
                              >
                                <span className="text-emerald-800">
                                  {sourceLabels[s.source] ?? s.source}
                                </span>
                                <span className="text-emerald-900 tabular-nums">
                                  {s.total_tokens.toLocaleString()}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    ) : (
                      <p className="text-sm text-emerald-600/50">
                        暂无用量数据
                      </p>
                    )}
                  </CardContent>
                )}
              </Card>

              <BillingCard />

              <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <KeyRound className="size-4 text-emerald-600" />
                      <CardTitle className="text-base font-semibold text-emerald-950">
                        DeepSeek 模型
                      </CardTitle>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 text-emerald-600/70"
                      onClick={() => setDsOpen((v) => !v)}
                      title={dsOpen ? "收起" : "展开"}
                    >
                      {dsOpen ? (
                        <ChevronUp className="size-4" />
                      ) : (
                        <ChevronDown className="size-4" />
                      )}
                    </Button>
                  </div>
                </CardHeader>
                {dsOpen && (
                  <CardContent className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Input
                        type="password"
                        value={dsKeyInput}
                        onChange={(e) => setDsKeyInput(e.target.value)}
                        placeholder={
                          dsKeyPresent
                            ? "已配置，输入新 key 可更换"
                            : "请输入 DeepSeek API Key"
                        }
                        autoComplete="off"
                        className="h-9 border-emerald-200 focus-visible:ring-emerald-400"
                      />
                      <Button
                        onClick={handleSaveDsKey}
                        disabled={dsVerifying}
                        className="shrink-0 bg-emerald-600 text-white hover:bg-emerald-500"
                      >
                        {dsVerifying ? (
                          <Loader2 className="mr-1 size-4 animate-spin" />
                        ) : (
                          <Save className="mr-1 size-4" />
                        )}
                        保存并校验
                      </Button>
                      {dsKeyPresent && (
                        <Button
                          variant="outline"
                          onClick={handleClearDsKey}
                          className="shrink-0 border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                        >
                          清除
                        </Button>
                      )}
                    </div>

                    {dsKeyPresent && (
                      <p className="flex items-center gap-1.5 text-xs text-emerald-700">
                        <CheckCircle2 className="size-3.5 text-emerald-500" />
                        已配置 DeepSeek Key
                        {dsExpiry
                          ? `（${new Date(dsExpiry).toLocaleDateString()} 过期）`
                          : ""}
                        ，对话将使用 DeepSeek 模型；失效时自动回退默认模型
                      </p>
                    )}
                    {dsMsg && (
                      <p className="text-xs text-emerald-600">{dsMsg}</p>
                    )}
                    {dsError && (
                      <p className="text-xs text-red-500">{dsError}</p>
                    )}

                    <p className="rounded-lg bg-emerald-50/50 px-3 py-2 text-xs leading-relaxed text-emerald-700/70">
                      说明：DeepSeek Key 仅保存在<b>本机浏览器</b>
                      （localStorage）， 15
                      天后需重新填写；不会上传服务器存储。配置后对话将优先使用
                      DeepSeek 视觉模型，key 无效时自动回退默认模型。
                    </p>
                  </CardContent>
                )}
              </Card>

              <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                <CardHeader>
                  <div className="flex items-center justify-between gap-2">
                    <CardTitle className="text-base font-semibold text-emerald-950">
                      账号与安全
                    </CardTitle>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 text-emerald-600/70"
                      onClick={() => setSecurityOpen((v) => !v)}
                      title={securityOpen ? "收起" : "展开"}
                    >
                      {securityOpen ? (
                        <ChevronUp className="size-4" />
                      ) : (
                        <ChevronDown className="size-4" />
                      )}
                    </Button>
                  </div>
                </CardHeader>
                {securityOpen && (
                  <CardContent className="space-y-5">
                    {/* ---------- 换绑手机号 ---------- */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="text-sm font-medium text-emerald-800">
                            手机号
                          </p>
                          <p className="text-xs text-emerald-600/60">
                            {maskPhone(profile?.phone)}
                          </p>
                        </div>
                        {changeStep === 0 && (
                          <Button
                            variant="outline"
                            onClick={() => {
                              setChangeError("")
                              setChangeMsg("")
                              setChangeStep(1)
                            }}
                            className="border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                          >
                            <Smartphone className="mr-1 size-4" />
                            换绑手机号
                          </Button>
                        )}
                      </div>

                      {changeStep > 0 && (
                        <div className="space-y-3 rounded-xl bg-emerald-50/40 p-3">
                          {changeStep === 1 ? (
                            <>
                              <p className="text-xs text-emerald-700/70">
                                第 1 步：验证旧手机号（
                                {maskPhone(profile?.phone)}）
                              </p>
                              <div className="flex items-center gap-2">
                                <Input
                                  value={oldCode}
                                  onChange={(e) =>
                                    setOldCode(
                                      e.target.value.replace(/\D/g, "")
                                    )
                                  }
                                  placeholder="旧号短信验证码"
                                  maxLength={4}
                                  inputMode="numeric"
                                  className="border-emerald-200"
                                />
                                <Button
                                  onClick={sendOldCode}
                                  disabled={
                                    oldCountdown.countdown > 0 || sendingOld
                                  }
                                  variant="outline"
                                  className="shrink-0 border-emerald-200 text-emerald-700"
                                >
                                  {sendingOld
                                    ? "发送中…"
                                    : oldCountdown.countdown > 0
                                      ? `${oldCountdown.countdown}s 后重发`
                                      : "获取验证码"}
                                </Button>
                              </div>
                              <Button
                                onClick={() => setChangeStep(2)}
                                disabled={oldCode.length !== 4}
                                className="w-full bg-emerald-600 text-white hover:bg-emerald-500"
                              >
                                下一步
                              </Button>
                              <Button
                                onClick={cancelChange}
                                variant="ghost"
                                className="w-full text-emerald-600/70 hover:bg-emerald-100/60 hover:text-emerald-700"
                              >
                                取消
                              </Button>
                            </>
                          ) : (
                            <>
                              <p className="text-xs text-emerald-700/70">
                                第 2 步：绑定新手机号
                              </p>
                              <Input
                                value={newPhone}
                                onChange={(e) =>
                                  setNewPhone(e.target.value.replace(/\D/g, ""))
                                }
                                placeholder="请输入 11 位新手机号"
                                maxLength={11}
                                inputMode="numeric"
                                className="border-emerald-200"
                              />
                              <div className="flex items-center gap-2">
                                <Input
                                  value={newCode}
                                  onChange={(e) =>
                                    setNewCode(
                                      e.target.value.replace(/\D/g, "")
                                    )
                                  }
                                  placeholder="新号短信验证码"
                                  maxLength={4}
                                  inputMode="numeric"
                                  className="border-emerald-200"
                                />
                                <Button
                                  onClick={sendNewCode}
                                  disabled={
                                    newCountdown.countdown > 0 ||
                                    sendingNew ||
                                    newPhone.length !== 11
                                  }
                                  variant="outline"
                                  className="shrink-0 border-emerald-200 text-emerald-700"
                                >
                                  {sendingNew
                                    ? "发送中…"
                                    : newCountdown.countdown > 0
                                      ? `${newCountdown.countdown}s 后重发`
                                      : "获取验证码"}
                                </Button>
                              </div>
                              <div className="flex gap-2">
                                <Button
                                  onClick={() => setChangeStep(1)}
                                  variant="outline"
                                  className="border-emerald-200 text-emerald-700"
                                >
                                  上一步
                                </Button>
                                <Button
                                  onClick={cancelChange}
                                  variant="outline"
                                  className="border-emerald-200 text-emerald-700"
                                >
                                  取消
                                </Button>
                                <Button
                                  onClick={submitChangePhone}
                                  disabled={
                                    changeSubmitting || newCode.length !== 4
                                  }
                                  className="flex-1 bg-emerald-600 text-white hover:bg-emerald-500"
                                >
                                  {changeSubmitting && (
                                    <Loader2 className="mr-2 size-4 animate-spin" />
                                  )}
                                  确认换绑
                                </Button>
                              </div>
                            </>
                          )}
                          {changeError && (
                            <p className="text-sm text-red-500">
                              {changeError}
                            </p>
                          )}
                          {changeMsg && (
                            <p className="text-sm text-emerald-600">
                              {changeMsg}
                            </p>
                          )}
                        </div>
                      )}
                    </div>

                    <div className="h-px bg-emerald-100" />

                    {/* ---------- 注销账号（危险区） ---------- */}
                    <div className="rounded-xl border border-red-200 bg-red-50/60 p-4">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="size-4 text-red-500" />
                        <p className="text-sm font-semibold text-red-700">
                          危险操作
                        </p>
                      </div>
                      <p className="mt-1 text-xs text-red-600/80">
                        注销账号将立即删除你的全部个人数据（计划、打卡、饮食、身体指标、对话、记忆等），不可恢复。
                      </p>
                      <Button
                        onClick={() => {
                          setDeactError("")
                          setDeactPassword("")
                          setDeactCode("")
                          setDeactOpen(true)
                        }}
                        className="mt-3 bg-red-600 text-white hover:bg-red-500"
                      >
                        <Trash2 className="mr-1 size-4" />
                        注销账号
                      </Button>
                    </div>
                  </CardContent>
                )}
              </Card>

              <Dialog open={deactOpen} onOpenChange={setDeactOpen}>
                <DialogContent className="border-red-200 sm:max-w-sm">
                  <DialogHeader>
                    <DialogTitle className="text-red-700">
                      确认注销账号？
                    </DialogTitle>
                    <DialogDescription asChild>
                      <div className="space-y-2 text-sm">
                        <p>
                          此操作将<b className="text-red-600">立即删除</b>
                          你的全部个人数据，不可恢复。请输入密码并完成短信验证以确认。
                        </p>
                      </div>
                    </DialogDescription>
                  </DialogHeader>
                  <div className="space-y-3">
                    <Input
                      type="password"
                      value={deactPassword}
                      onChange={(e) => setDeactPassword(e.target.value)}
                      placeholder="登录密码"
                      className="border-red-200"
                    />
                    <div className="flex items-center gap-2">
                      <Input
                        value={deactCode}
                        onChange={(e) =>
                          setDeactCode(e.target.value.replace(/\D/g, ""))
                        }
                        placeholder={`短信验证码（发至 ${maskPhone(profile?.phone)}）`}
                        maxLength={4}
                        inputMode="numeric"
                        className="border-red-200"
                      />
                      <Button
                        onClick={sendDeactCode}
                        disabled={deactCountdown.countdown > 0 || sendingDeact}
                        variant="outline"
                        className="shrink-0 border-red-200 text-red-600 hover:bg-red-50"
                      >
                        {sendingDeact
                          ? "发送中…"
                          : deactCountdown.countdown > 0
                            ? `${deactCountdown.countdown}s 后重发`
                            : "获取验证码"}
                      </Button>
                    </div>
                    {deactError && (
                      <p className="text-sm text-red-500">{deactError}</p>
                    )}
                  </div>
                  <DialogFooter>
                    <Button
                      variant="outline"
                      onClick={() => setDeactOpen(false)}
                    >
                      取消
                    </Button>
                    <Button
                      onClick={submitDeactivate}
                      disabled={
                        deactSubmitting ||
                        !deactPassword ||
                        deactCode.length !== 4
                      }
                      className="bg-red-600 text-white hover:bg-red-500"
                    >
                      {deactSubmitting && (
                        <Loader2 className="mr-2 size-4 animate-spin" />
                      )}
                      确认注销
                    </Button>
                  </DialogFooter>
                </DialogContent>
              </Dialog>

              <ApiKeyPanel />
            </>
          )}
        </div>
      </div>
    </AppLayout>
  )
}
