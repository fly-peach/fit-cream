/**
 * 健身画像卡（个人中心）
 *
 * 自取数据 GET /users/me/fitness-profile，按 5 个 tab 分组展示 Intake 五维，
 * 全字段可编辑（与 FormCard 不同：档案已存值也可修改），每 tab 独立保存
 * PUT /users/me/fitness-profile（仅提交该维度有值字段）。
 *
 * 字段定义单一来源 form-templates.ts（key/label/type/options 与聊天表单一致）。
 */
import { useEffect, useMemo, useState } from "react";
import { CheckCircle2, Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { FORM_TEMPLATES, type FormFieldDef } from "@/components/form-templates";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type ProfileValue = string | number | null;

interface FitnessProfile {
  id: string;
  user_id: string;
  medical_history: string | null;
  injuries: string | null;
  allergies: string | null;
  pregnancy: string | null;
  medication: string | null;
  parq_result: string | null;
  doctor_advice: string | null;
  training_experience: string | null;
  cardio_level: string | null;
  strength_level: string | null;
  flexibility: string | null;
  body_fat_pct: number | null;
  weekly_frequency: string | null;
  session_duration: string | null;
  preferred_types: string | null;
  past_results: string | null;
  occupation_schedule: string | null;
  diet_habits: string | null;
  sleep_quality: string | null;
  stress_level: string | null;
  equipment: string | null;
  preferred_time: string | null;
  diet_preferences: string | null;
  food_allergies: string | null;
  cooking_condition: string | null;
  meals_per_day: string | null;
  eating_out_ratio: string | null;
  budget: string | null;
}

const TABS: { id: string; label: string }[] = [
  { id: "health_safety", label: "健康与安全" },
  { id: "fitness_level", label: "体能水平" },
  { id: "exercise_history", label: "运动经历" },
  { id: "lifestyle", label: "生活方式" },
  { id: "diet_profile", label: "饮食偏好" },
];

function optionLabel(field: FormFieldDef, value: string): string {
  return field.options?.find((o) => o.value === value)?.label ?? value;
}

export function FitnessProfileCard() {
  const [profile, setProfile] = useState<FitnessProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [savingTab, setSavingTab] = useState<string | null>(null);
  const [savedTab, setSavedTab] = useState<string | null>(null);

  useEffect(() => {
    api
      .get<FitnessProfile>("/users/me/fitness-profile")
      .then((data) => {
        setProfile(data);
        const init: Record<string, string> = {};
        for (const [k, v] of Object.entries(data)) {
          if (v !== null && v !== undefined) init[k] = String(v);
        }
        setValues(init);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const setValue = (key: string, v: string) =>
    setValues((prev) => ({ ...prev, [key]: v }));

  const handleSave = async (tabId: string) => {
    const fields = FORM_TEMPLATES[tabId]?.fields ?? [];
    const payload: Record<string, ProfileValue> = {};
    for (const f of fields) {
      const raw = (values[f.key] ?? "").trim();
      if (!raw) continue;
      if (f.type === "number") {
        const n = Number(raw);
        if (Number.isFinite(n)) payload[f.key] = n;
      } else {
        payload[f.key] = raw;
      }
    }
    setSavingTab(tabId);
    setError("");
    try {
      const updated = await api.put<FitnessProfile>("/users/me/fitness-profile", payload);
      setProfile(updated);
      setSavedTab(tabId);
      setTimeout(() => setSavedTab(null), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSavingTab(null);
    }
  };

  const filledCount = useMemo(
    () => (profile ? Object.values(profile).filter((v) => v !== null && v !== "").length : 0),
    [profile]
  );

  return (
    <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader>
        <CardTitle className="text-base font-semibold text-emerald-950">
          健身画像
        </CardTitle>
        {profile && filledCount > 0 && (
          <p className="text-xs text-emerald-600/60">
            已填写 {filledCount} 项，聊天与计划设计共用这份档案
          </p>
        )}
      </CardHeader>
      <CardContent className="space-y-3">
        {error && <p className="text-sm text-red-500">{error}</p>}

        {loading ? (
          <div className="flex items-center justify-center py-10 text-emerald-500">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : (
          <Tabs defaultValue="health_safety">
            <TabsList className="w-full bg-emerald-50">
              {TABS.map((t) => (
                <TabsTrigger key={t.id} value={t.id} className="flex-1">
                  {t.label}
                </TabsTrigger>
              ))}
            </TabsList>

            {TABS.map((t) => {
              const fields = FORM_TEMPLATES[t.id]?.fields ?? [];
              return (
                <TabsContent key={t.id} value={t.id} className="mt-3 space-y-3">
                  {fields.map((f) => {
                    const value = values[f.key] ?? "";
                    return (
                      <div key={f.key} className="space-y-1">
                        <label className="text-xs font-medium text-emerald-900">
                          {f.label}
                        </label>
                        {f.hint && (
                          <p className="text-[11px] text-muted-foreground">{f.hint}</p>
                        )}
                        {f.type === "select" ? (
                          <Select
                            value={value || undefined}
                            onValueChange={(v) => setValue(f.key, v ?? "")}
                          >
                            <SelectTrigger
                              className={cn(
                                "h-9 border-emerald-200 text-sm",
                                !value && "text-muted-foreground"
                              )}
                            >
                              <SelectValue placeholder="未填写">
                                {value ? optionLabel(f, value) : undefined}
                              </SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                              {(f.options || []).map((o) => (
                                <SelectItem key={o.value} value={o.value}>
                                  {o.label}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        ) : f.type === "textarea" ? (
                          <Textarea
                            value={value}
                            onChange={(e) => setValue(f.key, e.target.value)}
                            placeholder={f.placeholder || "未填写"}
                            rows={2}
                            className="border-emerald-200 text-sm"
                          />
                        ) : (
                          <div className="relative">
                            <Input
                              type={f.type === "number" ? "number" : "text"}
                              value={value}
                              onChange={(e) => setValue(f.key, e.target.value)}
                              placeholder={f.placeholder || "未填写"}
                              className="h-9 border-emerald-200 text-sm"
                            />
                            {f.unit && (
                              <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">
                                {f.unit}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  <div className="flex items-center justify-between pt-1">
                    <span className="text-[11px] text-muted-foreground">
                      留空的字段不会覆盖档案中的原值
                    </span>
                    <Button
                      size="sm"
                      onClick={() => handleSave(t.id)}
                      disabled={savingTab === t.id}
                      className="bg-emerald-600 text-white hover:bg-emerald-700"
                    >
                      {savingTab === t.id ? (
                        <Loader2 className="mr-1 size-3.5 animate-spin" />
                      ) : savedTab === t.id ? (
                        <CheckCircle2 className="mr-1 size-3.5" />
                      ) : (
                        <Save className="mr-1 size-3.5" />
                      )}
                      {savedTab === t.id ? "已保存" : "保存"}
                    </Button>
                  </div>
                </TabsContent>
              );
            })}
          </Tabs>
        )}
      </CardContent>
    </Card>
  );
}
