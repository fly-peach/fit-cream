import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { format } from "date-fns";
import { ResponsiveContainer, RadialBarChart, RadialBar, PolarAngleAxis } from "recharts";
import { Card, CardContent } from "@/components/ui/card";
import { Flame, Footprints, Utensils, Pencil, Check, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

interface UserProfile {
  gender?: string | null;
  age?: number | null;
  weight_kg?: number | null;
  height_cm?: number | null;
}

interface UserSettings {
  calorie_goal: number;
  protein_goal_g: number;
  carbs_goal_g: number;
  fat_goal_g: number;
  weekly_training_goal: number;
}

interface DietMealRecord {
  calories: number;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
}

type MacroKey = "protein_goal_g" | "carbs_goal_g" | "fat_goal_g";

function calcBmr(p: UserProfile): number | null {
  const w = p.weight_kg;
  const h = p.height_cm;
  const a = p.age;
  if (w == null || h == null || a == null) return null;
  const base = 10 * w + 6.25 * h - 5 * a;
  if (p.gender === "male") return Math.round(base + 5);
  if (p.gender === "female") return Math.round(base - 161);
  return Math.round(base - 78);
}

export function TodayOverviewBar({
  trainingCalories,
  trainingDuration,
}: {
  trainingCalories?: number | null;
  trainingDuration?: number | null;
}) {
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [totals, setTotals] = useState({
    calories: 0,
    protein: 0,
    carbs: 0,
    fat: 0,
  });
  const [editingKey, setEditingKey] = useState<MacroKey | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const editInputRef = useRef<HTMLInputElement>(null);
  const [editingCalorie, setEditingCalorie] = useState(false);
  const [calorieEditValue, setCalorieEditValue] = useState("");
  const calorieInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const today = format(new Date(), "yyyy-MM-dd");
    Promise.all([
      api.get<UserSettings>("/users/settings").catch(() => null),
      api.get<UserProfile>("/users/me").catch(() => null),
      api
        .get<{ items: DietMealRecord[] }>(`/diet-meals?start=${today}&end=${today}&size=100`)
        .catch(() => null),
    ]).then(([s, p, mealRes]) => {
      if (s) setSettings(s);
      if (p) setProfile(p);
      const items = mealRes?.items ?? [];
      setTotals(
        items.reduce(
          (acc, m) => ({
            calories: acc.calories + (m.calories || 0),
            protein: acc.protein + (m.protein_g || 0),
            carbs: acc.carbs + (m.carbs_g || 0),
            fat: acc.fat + (m.fat_g || 0),
          }),
          { calories: 0, protein: 0, carbs: 0, fat: 0 },
        ),
      );
    });
  }, []);

  useEffect(() => {
    if (editingKey && editInputRef.current) {
      editInputRef.current.focus();
      editInputRef.current.select();
    }
  }, [editingKey]);

  useEffect(() => {
    if (editingCalorie && calorieInputRef.current) {
      calorieInputRef.current.focus();
      calorieInputRef.current.select();
    }
  }, [editingCalorie]);

  const startEdit = (key: MacroKey, currentVal: number) => {
    setEditingKey(key);
    setEditValue(String(currentVal));
  };

  const cancelEdit = () => {
    setEditingKey(null);
    setEditValue("");
  };

  const saveEdit = async (key: MacroKey) => {
    const num = parseFloat(editValue);
    if (isNaN(num) || num < 0) {
      cancelEdit();
      return;
    }
    setSaving(true);
    try {
      const updated = await api.put<UserSettings>("/users/settings", { [key]: num });
      if (updated) setSettings(updated);
    } catch {
      // silent
    } finally {
      setSaving(false);
      setEditingKey(null);
    }
  };

  const startCalorieEdit = () => {
    setEditingCalorie(true);
    setCalorieEditValue(String(targetCalories));
  };

  const cancelCalorieEdit = () => {
    setEditingCalorie(false);
    setCalorieEditValue("");
  };

  const saveCalorieEdit = async () => {
    const num = parseInt(calorieEditValue, 10);
    if (isNaN(num) || num < 500 || num > 10000) {
      cancelCalorieEdit();
      return;
    }
    setSaving(true);
    try {
      const updated = await api.put<UserSettings>("/users/settings", { calorie_goal: num });
      if (updated) setSettings(updated);
    } catch {
      // silent
    } finally {
      setSaving(false);
      setEditingCalorie(false);
    }
  };

  const bmr = useMemo(() => (profile ? calcBmr(profile) : null), [profile]);

  const targetCalories = settings?.calorie_goal ?? 2000;
  const consumed = totals.calories;
  const remaining = targetCalories - consumed;
  const percent =
    targetCalories > 0 ? Math.min(100, Math.round((consumed / targetCalories) * 100)) : 0;

  const macros: {
    label: string;
    value: number;
    target: number;
    color: string;
    key: MacroKey;
  }[] = [
    {
      label: "蛋白质",
      value: totals.protein,
      target: settings?.protein_goal_g ?? 0,
      color: "bg-emerald-500",
      key: "protein_goal_g",
    },
    {
      label: "碳水",
      value: totals.carbs,
      target: settings?.carbs_goal_g ?? 0,
      color: "bg-amber-500",
      key: "carbs_goal_g",
    },
    {
      label: "脂肪",
      value: totals.fat,
      target: settings?.fat_goal_g ?? 0,
      color: "bg-sky-500",
      key: "fat_goal_g",
    },
  ];

  return (
    <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
      <CardContent className="p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-6">
          {/* 环形热量图 */}
          <div className="flex items-center gap-4 sm:gap-5">
            <div className="relative size-24 shrink-0 sm:size-28">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart
                  innerRadius="78%"
                  outerRadius="100%"
                  data={[{ name: "calories", value: percent, fill: "#f59e0b" }]}
                  startAngle={90}
                  endAngle={-270}
                >
                  <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                  <RadialBar background={{ fill: "#fef3c7" }} cornerRadius={10} dataKey="value" />
                </RadialBarChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                {editingCalorie ? (
                  <div className="flex flex-col items-center gap-0.5">
                    <span className="text-sm font-bold tabular-nums text-emerald-950">
                      {consumed}
                    </span>
                    <div className="flex items-center gap-0.5">
                      <input
                        ref={calorieInputRef}
                        type="number"
                        min={500}
                        max={10000}
                        step={50}
                        value={calorieEditValue}
                        onChange={(e) => setCalorieEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            saveCalorieEdit();
                          } else if (e.key === "Escape") {
                            cancelCalorieEdit();
                          }
                        }}
                        disabled={saving}
                        className="h-4 w-12 rounded border border-amber-200 bg-white px-1 text-right text-[10px] tabular-nums text-emerald-800 outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-200"
                      />
                      <button
                        type="button"
                        onClick={saveCalorieEdit}
                        disabled={saving}
                        className="flex size-4 items-center justify-center rounded text-emerald-600 transition-colors hover:bg-emerald-100"
                        title="保存"
                      >
                        <Check className="size-3" />
                      </button>
                      <button
                        type="button"
                        onClick={cancelCalorieEdit}
                        className="flex size-4 items-center justify-center rounded text-emerald-400 transition-colors hover:bg-red-50 hover:text-red-500"
                        title="取消"
                      >
                        <X className="size-3" />
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={startCalorieEdit}
                    className="group/cal flex flex-col items-center justify-center rounded"
                    title="点击编辑目标热量"
                  >
                    <span className="text-base font-bold tabular-nums text-emerald-950 sm:text-lg">
                      {consumed}
                    </span>
                    <span className="flex items-center gap-0.5 text-[10px] text-emerald-600/60">
                      / {targetCalories}
                      <Pencil className="size-2.5 text-emerald-300 opacity-100 transition-opacity sm:opacity-0 sm:group-hover/cal:opacity-100" />
                    </span>
                  </button>
                )}
              </div>
            </div>
            <div className="min-w-0">
              <p className="text-xs text-emerald-600/60">今日能量</p>
              <p
                className={cn(
                  "text-lg font-bold tabular-nums sm:text-xl",
                  remaining >= 0 ? "text-emerald-600" : "text-red-500",
                )}
              >
                {remaining >= 0 ? `还差 ${remaining} kcal` : `超出 ${Math.abs(remaining)} kcal`}
              </p>
              <p className="mt-0.5 text-[11px] text-emerald-500/60">已摄入 {consumed} kcal</p>
            </div>
          </div>

          {/* 三大营养素进度条 */}
          <div className="flex-1 space-y-2.5">
            {macros.map((m) => {
              const pct =
                m.target > 0 ? Math.min(100, Math.round((m.value / m.target) * 100)) : 0;
              const isEditing = editingKey === m.key;
              return (
                <div key={m.label} className="flex items-center gap-2">
                  <span className="w-9 shrink-0 text-xs text-emerald-700">{m.label}</span>
                  <div className="h-2 flex-1 overflow-hidden rounded-full bg-emerald-100/70">
                    <div
                      className={cn("h-full rounded-full transition-all", m.color)}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  {isEditing ? (
                    <span className="flex shrink-0 items-center gap-1">
                      <span className="text-[11px] tabular-nums text-emerald-600/70">
                        {Math.round(m.value * 10) / 10} /
                      </span>
                      <input
                        ref={editInputRef}
                        type="number"
                        min={0}
                        step={1}
                        value={editValue}
                        onChange={(e) => setEditValue(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            saveEdit(m.key);
                          } else if (e.key === "Escape") {
                            cancelEdit();
                          }
                        }}
                        disabled={saving}
                        className="h-5 w-12 rounded border border-emerald-200 bg-white px-1 text-right text-[11px] tabular-nums text-emerald-800 outline-none focus:border-emerald-400 focus:ring-1 focus:ring-emerald-200"
                      />
                      <span className="text-[11px] text-emerald-600/70">g</span>
                      <button
                        type="button"
                        onClick={() => saveEdit(m.key)}
                        disabled={saving}
                        className="flex size-4 items-center justify-center rounded text-emerald-600 transition-colors hover:bg-emerald-100"
                        title="保存"
                      >
                        <Check className="size-3" />
                      </button>
                      <button
                        type="button"
                        onClick={cancelEdit}
                        className="flex size-4 items-center justify-center rounded text-emerald-400 transition-colors hover:bg-red-50 hover:text-red-500"
                        title="取消"
                      >
                        <X className="size-3" />
                      </button>
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => startEdit(m.key, m.target)}
                      className="group/target flex w-20 shrink-0 items-center justify-end gap-0.5 rounded px-0.5 text-right transition-colors hover:bg-emerald-50"
                      title="点击编辑目标值"
                    >
                      <span className="text-[11px] tabular-nums text-emerald-600/70">
                        {Math.round(m.value * 10) / 10} / {m.target} g
                      </span>
                      <Pencil className="size-2.5 text-emerald-300 opacity-100 transition-opacity sm:opacity-0 sm:group-hover/target:opacity-100" />
                    </button>
                  )}
                </div>
              );
            })}

            {/* 基础代谢 + 训练消耗 */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1 pt-1 text-[11px] text-emerald-600/70">
              <span className="inline-flex items-center gap-1">
                <Flame className="size-3.5 text-orange-400" />
                基础代谢 {bmr != null ? `${bmr} kcal` : "--"}
              </span>
              <span className="inline-flex items-center gap-1">
                <Footprints className="size-3.5 text-emerald-500" />
                训练消耗{" "}
                {trainingCalories != null
                  ? `${trainingCalories} kcal`
                  : trainingDuration != null
                    ? `${trainingDuration} 分钟`
                    : "--"}
              </span>
              <Link
                to="/plans"
                className="inline-flex items-center gap-1 rounded-md bg-orange-50 px-2 py-1 font-medium text-orange-700 transition-colors hover:bg-orange-100"
              >
                <Utensils className="size-3" />
                去记录饮食
              </Link>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
