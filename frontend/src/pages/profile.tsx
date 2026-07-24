import { useEffect, useState } from "react";
import { AppLayout } from "@/components/app-layout";
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
import { User, Save, Loader2, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";

interface UserProfile {
  id: string;
  phone: string | null;
  email: string | null;
  name: string | null;
  height_cm: number | null;
  weight_kg: number | null;
  age: number | null;
  gender: string | null;
  goal: string | null;
  created_at: string;
}

const genderOptions = [
  { value: "male", label: "男" },
  { value: "female", label: "女" },
  { value: "other", label: "其他" },
];

const goalOptions = [
  { value: "lose_fat", label: "减脂塑形" },
  { value: "gain_muscle", label: "增肌增重" },
  { value: "maintain", label: "保持健康" },
  { value: "improve_health", label: "改善体质" },
];

export default function ProfilePage() {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [form, setForm] = useState({
    name: "",
    height_cm: "",
    weight_kg: "",
    age: "",
    gender: "",
    goal: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .get<UserProfile>("/users/me")
      .then((data) => {
        setProfile(data);
        setForm({
          name: data.name ?? "",
          height_cm: data.height_cm?.toString() ?? "",
          weight_kg: data.weight_kg?.toString() ?? "",
          age: data.age?.toString() ?? "",
          gender: data.gender ?? "",
          goal: data.goal ?? "",
        });
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      const payload: Record<string, unknown> = {
        name: form.name || null,
        gender: form.gender || null,
        goal: form.goal || null,
      };
      if (form.height_cm) payload.height_cm = Number(form.height_cm);
      if (form.weight_kg) payload.weight_kg = Number(form.weight_kg);
      if (form.age) payload.age = Number(form.age);

      const updated = await api.put<UserProfile>("/users/me", payload);
      setProfile(updated);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const bmi =
    profile?.height_cm && profile?.weight_kg
      ? (profile.weight_kg / Math.pow(profile.height_cm / 100, 2)).toFixed(1)
      : null;

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-6 p-6">
          <header className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-100">
              <User className="size-5 text-emerald-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-emerald-950">个人中心</h1>
              <p className="text-sm text-emerald-600/60">管理你的身体数据与健身目标</p>
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
                      <p className="text-2xl font-bold text-emerald-600">{bmi}</p>
                    </div>
                  </CardContent>
                </Card>
              )}

              <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                <CardHeader>
                  <CardTitle className="text-base font-semibold text-emerald-950">
                    基本资料
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-emerald-800">昵称</label>
                      <Input
                        value={form.name}
                        onChange={(e) => setForm({ ...form, name: e.target.value })}
                        placeholder="请输入昵称"
                        className="border-emerald-200 focus-visible:ring-emerald-400"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-emerald-800">年龄</label>
                      <Input
                        type="number"
                        value={form.age}
                        onChange={(e) => setForm({ ...form, age: e.target.value })}
                        placeholder="请输入年龄"
                        className="border-emerald-200 focus-visible:ring-emerald-400"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-emerald-800">身高 (cm)</label>
                      <Input
                        type="number"
                        value={form.height_cm}
                        onChange={(e) => setForm({ ...form, height_cm: e.target.value })}
                        placeholder="请输入身高"
                        className="border-emerald-200 focus-visible:ring-emerald-400"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-emerald-800">体重 (kg)</label>
                      <Input
                        type="number"
                        value={form.weight_kg}
                        onChange={(e) => setForm({ ...form, weight_kg: e.target.value })}
                        placeholder="请输入体重"
                        className="border-emerald-200 focus-visible:ring-emerald-400"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-emerald-800">性别</label>
                      <Select
                        value={form.gender}
                        onValueChange={(v) => setForm({ ...form, gender: v ?? "" })}
                      >
                        <SelectTrigger className="border-emerald-200 focus:ring-emerald-400">
                          <SelectValue placeholder="请选择性别">
                            {genderOptions.find((o) => o.value === form.gender)?.label}
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
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-emerald-800">健身目标</label>
                      <Select
                        value={form.goal}
                        onValueChange={(v) => setForm({ ...form, goal: v ?? "" })}
                      >
                        <SelectTrigger className="border-emerald-200 focus:ring-emerald-400">
                          <SelectValue placeholder="请选择目标">
                            {goalOptions.find((o) => o.value === form.goal)?.label}
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
                </CardContent>
              </Card>
            </>
          )}
        </div>
      </div>
    </AppLayout>
  );
}