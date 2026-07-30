import { useEffect, useMemo, useState } from "react";
import { format } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  UtensilsCrossed,
  Loader2,
  Trash2,
  Pencil,
  Plus,
  Flame,
  Settings2,
  Check,
  Download,
} from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

// ============ Types ============

interface DietMealRecord {
  id: string;
  meal_date: string;
  meal_type: string;
  food_name: string;
  portion: string | null;
  calories: number;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  note: string | null;
}

interface UserSettings {
  calorie_goal: number;
  protein_goal_g: number;
  carbs_goal_g: number;
  fat_goal_g: number;
}

interface Totals {
  calories: number;
  protein: number;
  carbs: number;
  fat: number;
}

interface PlanMeal {
  id: string;
  meal_type: string;
  food_name: string;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  portion: string | null;
}

interface PlanDay {
  id: string;
  day_of_week: number;
  meals: PlanMeal[];
}

// ============ Constants ============

const mealTypeLabels: Record<string, string> = {
  breakfast: "早餐",
  lunch: "午餐",
  dinner: "晚餐",
  snack: "加餐",
};

const mealTypeOrder = ["breakfast", "lunch", "dinner", "snack"];

const mealTypeColors: Record<string, string> = {
  breakfast: "bg-amber-100 text-amber-700",
  lunch: "bg-emerald-100 text-emerald-700",
  dinner: "bg-sky-100 text-sky-700",
  snack: "bg-purple-100 text-purple-700",
};

const macroMeta: Record<
  "protein" | "carbs" | "fat",
  { label: string; color: string; key: keyof Totals; unit: string }
> = {
  protein: { label: "蛋白质", color: "bg-emerald-500", key: "protein", unit: "g" },
  carbs: { label: "碳水", color: "bg-amber-500", key: "carbs", unit: "g" },
  fat: { label: "脂肪", color: "bg-sky-500", key: "fat", unit: "g" },
};

// ============ 宏量进度条 ============

function MacroBar({
  label,
  value,
  target,
  color,
  unit,
}: {
  label: string;
  value: number;
  target: number;
  color: string;
  unit: string;
}) {
  const pct = target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;
  const met = target > 0 && value >= target;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="flex items-center gap-1 font-medium text-emerald-800">
          {label}
          {met && <Check className="size-3 text-emerald-500" />}
        </span>
        <span className="tabular-nums text-emerald-600/70">
          {Math.round(value * 10) / 10}
          <span className="text-emerald-400"> / {target}</span> {unit}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-emerald-100/70">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

// ============ 餐食表单字段（添加/编辑共用） ============

function MealFormFields({
  mealType,
  setMealType,
  food,
  setFood,
  portion,
  setPortion,
  calories,
  setCalories,
  protein,
  setProtein,
  carbs,
  setCarbs,
  fat,
  setFat,
  note,
  setNote,
}: {
  mealType: string;
  setMealType: (v: string) => void;
  food: string;
  setFood: (v: string) => void;
  portion: string;
  setPortion: (v: string) => void;
  calories: string;
  setCalories: (v: string) => void;
  protein: string;
  setProtein: (v: string) => void;
  carbs: string;
  setCarbs: (v: string) => void;
  fat: string;
  setFat: (v: string) => void;
  note: string;
  setNote: (v: string) => void;
}) {
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1">
        {Object.entries(mealTypeLabels).map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => setMealType(key)}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              mealType === key
                ? mealTypeColors[key]
                : "bg-white text-emerald-600/70 hover:bg-emerald-50",
            )}
          >
            {label}
          </button>
        ))}
      </div>
      <Input
        value={food}
        onChange={(e) => setFood(e.target.value)}
        placeholder="食物名称（如 鸡胸肉）"
        className="h-8 text-sm"
      />
      <div className="grid grid-cols-2 gap-2">
        <div className="flex items-center gap-1">
          <Input
            type="number"
            min={0}
            value={calories}
            onChange={(e) => setCalories(e.target.value)}
            placeholder="热量"
            className="h-8 text-sm"
          />
          <span className="text-[10px] text-emerald-500">kcal</span>
        </div>
        <div className="flex items-center gap-1">
          <Input
            value={portion}
            onChange={(e) => setPortion(e.target.value)}
            placeholder="份量（如 150g）"
            className="h-8 text-sm"
          />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2">
        <div className="flex items-center gap-1">
          <Input
            type="number"
            min={0}
            step={0.1}
            value={protein}
            onChange={(e) => setProtein(e.target.value)}
            placeholder="蛋白质"
            className="h-8 text-sm"
          />
          <span className="text-[10px] text-emerald-500">g</span>
        </div>
        <div className="flex items-center gap-1">
          <Input
            type="number"
            min={0}
            step={0.1}
            value={carbs}
            onChange={(e) => setCarbs(e.target.value)}
            placeholder="碳水"
            className="h-8 text-sm"
          />
          <span className="text-[10px] text-emerald-500">g</span>
        </div>
        <div className="flex items-center gap-1">
          <Input
            type="number"
            min={0}
            step={0.1}
            value={fat}
            onChange={(e) => setFat(e.target.value)}
            placeholder="脂肪"
            className="h-8 text-sm"
          />
          <span className="text-[10px] text-emerald-500">g</span>
        </div>
      </div>
      <Textarea
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="备注（可选）"
        className="min-h-12 resize-none text-sm"
      />
    </div>
  );
}

// ============ 饮食记录区段（嵌入 plans 页） ============

export function DietRecordSection({ selectedDate }: { selectedDate: Date }) {
  const [meals, setMeals] = useState<DietMealRecord[]>([]);
  const [settings, setSettings] = useState<UserSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  // 目标编辑
  const [editingTargets, setEditingTargets] = useState(false);
  const [targetCal, setTargetCal] = useState("");
  const [targetProtein, setTargetProtein] = useState("");
  const [targetCarbs, setTargetCarbs] = useState("");
  const [targetFat, setTargetFat] = useState("");

  // 添加餐食
  const [adding, setAdding] = useState(false);
  const [addMealType, setAddMealType] = useState("breakfast");
  const [addFood, setAddFood] = useState("");
  const [addPortion, setAddPortion] = useState("");
  const [addCalories, setAddCalories] = useState("");
  const [addProtein, setAddProtein] = useState("");
  const [addCarbs, setAddCarbs] = useState("");
  const [addFat, setAddFat] = useState("");
  const [addNote, setAddNote] = useState("");

  // 编辑餐食
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editMealType, setEditMealType] = useState("breakfast");
  const [editFood, setEditFood] = useState("");
  const [editPortion, setEditPortion] = useState("");
  const [editCalories, setEditCalories] = useState("");
  const [editProtein, setEditProtein] = useState("");
  const [editCarbs, setEditCarbs] = useState("");
  const [editFat, setEditFat] = useState("");
  const [editNote, setEditNote] = useState("");

  const [hasActivePlan, setHasActivePlan] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [planMeals, setPlanMeals] = useState<PlanMeal[]>([]);
  const [selectedImportIds, setSelectedImportIds] = useState<Set<string>>(new Set());
  const [importing, setImporting] = useState(false);

  const dateStr = format(selectedDate, "yyyy-MM-dd");

  const refreshMeals = async () => {
    const res = await api
      .get<{ items: DietMealRecord[] }>(
        `/diet-meals?start=${dateStr}&end=${dateStr}&size=100`,
      )
      .catch(() => null);
    setMeals(res?.items ?? []);
  };

  useEffect(() => {
    api
      .get<UserSettings>("/users/settings")
      .then((s) => {
        setSettings(s);
        setTargetCal(String(s.calorie_goal));
        setTargetProtein(String(s.protein_goal_g));
        setTargetCarbs(String(s.carbs_goal_g));
        setTargetFat(String(s.fat_goal_g));
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    api
      .get("/diet-plans/active")
      .then(() => setHasActivePlan(true))
      .catch(() => setHasActivePlan(false));
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .get<{ items: DietMealRecord[] }>(
        `/diet-meals?start=${dateStr}&end=${dateStr}&size=100`,
      )
      .then((res) => {
        if (!cancelled) setMeals(res?.items ?? []);
      })
      .catch(() => {
        if (!cancelled) setMeals([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [dateStr]);

  const totals = useMemo<Totals>(
    () =>
      meals.reduce(
        (acc, m) => ({
          calories: acc.calories + (m.calories || 0),
          protein: acc.protein + (m.protein_g || 0),
          carbs: acc.carbs + (m.carbs_g || 0),
          fat: acc.fat + (m.fat_g || 0),
        }),
        { calories: 0, protein: 0, carbs: 0, fat: 0 },
      ),
    [meals],
  );

  const targetCalories = settings?.calorie_goal ?? 2000;
  const calPct =
    targetCalories > 0
      ? Math.min(100, Math.round((totals.calories / targetCalories) * 100))
      : 0;

  const mealsByType = useMemo(() => {
    const map: Record<string, DietMealRecord[]> = {};
    for (const t of mealTypeOrder) map[t] = [];
    for (const m of meals) {
      (map[m.meal_type] ??= []).push(m);
    }
    return map;
  }, [meals]);

  const saveTargets = async () => {
    setSaving(true);
    try {
      const updated = await api.put<UserSettings>("/users/settings", {
        calorie_goal: parseInt(targetCal) || 2000,
        protein_goal_g: parseInt(targetProtein) || 0,
        carbs_goal_g: parseInt(targetCarbs) || 0,
        fat_goal_g: parseInt(targetFat) || 0,
      });
      setSettings(updated);
      setEditingTargets(false);
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const resetAddForm = () => {
    setAddMealType("breakfast");
    setAddFood("");
    setAddPortion("");
    setAddCalories("");
    setAddProtein("");
    setAddCarbs("");
    setAddFat("");
    setAddNote("");
  };

  const addMeal = async () => {
    if (!addFood.trim()) {
      alert("请填写食物名称");
      return;
    }
    setSaving(true);
    try {
      await api.post("/diet-meals", {
        meal_date: dateStr,
        meal_type: addMealType,
        food_name: addFood.trim(),
        portion: addPortion.trim() || null,
        calories: addCalories ? parseInt(addCalories) : 0,
        protein_g: addProtein ? parseFloat(addProtein) : null,
        carbs_g: addCarbs ? parseFloat(addCarbs) : null,
        fat_g: addFat ? parseFloat(addFat) : null,
        note: addNote.trim() || null,
      });
      resetAddForm();
      setAdding(false);
      await refreshMeals();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const startEdit = (m: DietMealRecord) => {
    setEditingId(m.id);
    setEditMealType(m.meal_type);
    setEditFood(m.food_name);
    setEditPortion(m.portion ?? "");
    setEditCalories(String(m.calories));
    setEditProtein(m.protein_g?.toString() ?? "");
    setEditCarbs(m.carbs_g?.toString() ?? "");
    setEditFat(m.fat_g?.toString() ?? "");
    setEditNote(m.note ?? "");
  };

  const saveEdit = async (id: string) => {
    setSaving(true);
    try {
      await api.put(`/diet-meals/${id}`, {
        meal_type: editMealType,
        food_name: editFood.trim(),
        portion: editPortion.trim() || null,
        calories: editCalories ? parseInt(editCalories) : 0,
        protein_g: editProtein ? parseFloat(editProtein) : null,
        carbs_g: editCarbs ? parseFloat(editCarbs) : null,
        fat_g: editFat ? parseFloat(editFat) : null,
        note: editNote.trim() || null,
      });
      setEditingId(null);
      await refreshMeals();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const deleteMeal = async (id: string) => {
    if (!confirm("确定删除该条饮食记录？")) return;
    try {
      await api.delete(`/diet-meals/${id}`);
      await refreshMeals();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const openImportDialog = async () => {
    setImportDialogOpen(true);
    setPlanMeals([]);
    setSelectedImportIds(new Set());
    try {
      const plan = await api.get<{ days: PlanDay[] }>("/diet-plans/active");
      const dow = selectedDate.getDay() === 0 ? 7 : selectedDate.getDay();
      const day = plan.days?.find((d) => d.day_of_week === dow);
      const meals = day?.meals ?? [];
      setPlanMeals(meals);
      setSelectedImportIds(new Set(meals.map((m) => m.id)));
    } catch {
      setPlanMeals([]);
    }
  };

  const toggleImportMeal = (id: string) => {
    setSelectedImportIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const confirmImport = async () => {
    const selected = planMeals.filter((m) => selectedImportIds.has(m.id));
    if (selected.length === 0) return;
    setImporting(true);
    try {
      await api.post("/diet-meals/batch", {
        meals: selected.map((m) => ({
          meal_date: dateStr,
          meal_type: m.meal_type,
          food_name: m.food_name,
          calories: m.calories ?? 0,
          protein_g: m.protein_g,
          carbs_g: m.carbs_g,
          fat_g: m.fat_g,
          portion: m.portion,
        })),
      });
      setImportDialogOpen(false);
      await refreshMeals();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-20 text-orange-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : (
            <>
              {/* 当日营养概览 */}
              <Card className="border-orange-100 bg-white/80 shadow-sm backdrop-blur">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base font-semibold text-orange-950">
                    <Flame className="size-4 text-orange-500" />
                    当日营养概览
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
                    {/* 热量环 */}
                    <div className="relative size-36 shrink-0">
                      <ResponsiveContainer width="100%" height="100%">
                        <RadialBarChart
                          innerRadius="72%"
                          outerRadius="100%"
                          data={[{ name: "calories", value: calPct, fill: "#f97316" }]}
                          startAngle={90}
                          endAngle={-270}
                        >
                          <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                          <RadialBar
                            background={{ fill: "#ffedd5" }}
                            cornerRadius={10}
                            dataKey="value"
                          />
                        </RadialBarChart>
                      </ResponsiveContainer>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-2xl font-bold tabular-nums text-orange-950">
                          {totals.calories}
                        </span>
                        <span className="text-[11px] text-orange-600/70">
                          / {targetCalories} kcal
                        </span>
                      </div>
                    </div>

                    {/* 三大宏量 */}
                    <div className="w-full flex-1 space-y-3">
                      {(["protein", "carbs", "fat"] as const).map((m) => {
                        const meta = macroMeta[m];
                        return (
                          <MacroBar
                            key={m}
                            label={meta.label}
                            value={totals[meta.key]}
                            target={
                              m === "protein"
                                ? settings?.protein_goal_g ?? 0
                                : m === "carbs"
                                  ? settings?.carbs_goal_g ?? 0
                                  : settings?.fat_goal_g ?? 0
                            }
                            color={meta.color}
                            unit={meta.unit}
                          />
                        );
                      })}
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* 营养目标 */}
              <Card className="border-orange-100 bg-white/80 shadow-sm backdrop-blur">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-base font-semibold text-orange-950">
                      <Settings2 className="size-4 text-orange-500" />
                      每日营养目标
                    </CardTitle>
                    {!editingTargets ? (
                      <Button
                        variant="ghost"
                        size="icon"
                        className="size-7 text-orange-400 hover:text-orange-600"
                        onClick={() => setEditingTargets(true)}
                      >
                        <Pencil className="size-3.5" />
                      </Button>
                    ) : null}
                  </div>
                </CardHeader>
                <CardContent>
                  {editingTargets ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            value={targetCal}
                            onChange={(e) => setTargetCal(e.target.value)}
                            className="h-8 text-sm"
                          />
                          <span className="text-[10px] text-orange-500">kcal</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            value={targetProtein}
                            onChange={(e) => setTargetProtein(e.target.value)}
                            placeholder="蛋白质"
                            className="h-8 text-sm"
                          />
                          <span className="text-[10px] text-orange-500">g</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            value={targetCarbs}
                            onChange={(e) => setTargetCarbs(e.target.value)}
                            placeholder="碳水"
                            className="h-8 text-sm"
                          />
                          <span className="text-[10px] text-orange-500">g</span>
                        </div>
                        <div className="flex items-center gap-1">
                          <Input
                            type="number"
                            value={targetFat}
                            onChange={(e) => setTargetFat(e.target.value)}
                            placeholder="脂肪"
                            className="h-8 text-sm"
                          />
                          <span className="text-[10px] text-orange-500">g</span>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          className="h-7 text-xs"
                          onClick={saveTargets}
                          disabled={saving}
                        >
                          {saving ? "保存中..." : "保存目标"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-xs"
                          onClick={() => setEditingTargets(false)}
                        >
                          取消
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      {(
                        [
                          { label: "热量", value: targetCalories, unit: "kcal" },
                          { label: "蛋白质", value: settings?.protein_goal_g ?? 0, unit: "g" },
                          { label: "碳水", value: settings?.carbs_goal_g ?? 0, unit: "g" },
                          { label: "脂肪", value: settings?.fat_goal_g ?? 0, unit: "g" },
                        ] as const
                      ).map((t) => (
                        <div
                          key={t.label}
                          className="rounded-lg bg-orange-50/60 px-3 py-2 text-center"
                        >
                          <p className="text-xs text-orange-600/70">{t.label}</p>
                          <p className="text-lg font-bold tabular-nums text-orange-950">
                            {t.value}
                            <span className="ml-0.5 text-xs font-normal text-orange-400">
                              {t.unit}
                            </span>
                          </p>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* 餐食记录 */}
              <Card className="border-orange-100 bg-white/80 shadow-sm backdrop-blur">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="flex items-center gap-2 text-base font-semibold text-orange-950">
                      <UtensilsCrossed className="size-4 text-orange-500" />
                      餐食记录（{meals.length}）
                    </CardTitle>
                    {!adding && (
                      <div className="flex gap-2">
                        {hasActivePlan && (
                          <Button
                            variant="outline"
                            size="sm"
                            className="border-orange-200 text-orange-700"
                            onClick={openImportDialog}
                          >
                            <Download className="mr-1 size-4" />
                            从计划导入
                          </Button>
                        )}
                        <Button
                          variant="outline"
                          size="sm"
                          className="border-orange-200 text-orange-700"
                          onClick={() => setAdding(true)}
                        >
                          <Plus className="mr-1 size-4" />
                          添加餐食
                        </Button>
                      </div>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* 添加餐食表单 */}
                  {adding && (
                    <div className="space-y-2 rounded-lg border border-orange-200 bg-orange-50/40 p-3">
                      <MealFormFields
                        mealType={addMealType}
                        setMealType={setAddMealType}
                        food={addFood}
                        setFood={setAddFood}
                        portion={addPortion}
                        setPortion={setAddPortion}
                        calories={addCalories}
                        setCalories={setAddCalories}
                        protein={addProtein}
                        setProtein={setAddProtein}
                        carbs={addCarbs}
                        setCarbs={setAddCarbs}
                        fat={addFat}
                        setFat={setAddFat}
                        note={addNote}
                        setNote={setAddNote}
                      />
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          className="h-7 text-xs"
                          onClick={addMeal}
                          disabled={saving}
                        >
                          {saving ? "添加中..." : "添加"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 text-xs"
                          onClick={() => {
                            setAdding(false);
                            resetAddForm();
                          }}
                        >
                          取消
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* 按餐次分组的餐食列表 */}
                  {meals.length === 0 && !adding ? (
                    <p className="py-8 text-center text-sm text-orange-600/50">
                      当天暂无饮食记录，点击「添加餐食」开始记录
                    </p>
                  ) : (
                    mealTypeOrder.map((mt) => {
                      const list = mealsByType[mt] ?? [];
                      if (list.length === 0) return null;
                      return (
                        <div key={mt} className="space-y-2">
                          <div className="flex items-center gap-2">
                            <Badge
                              className={cn(
                                "rounded-md px-2 py-0.5 text-xs font-medium",
                                mealTypeColors[mt] ?? "bg-gray-100 text-gray-600",
                              )}
                            >
                              {mealTypeLabels[mt] ?? mt}
                            </Badge>
                            <span className="text-xs text-orange-600/50">
                              {list.length} 项 · {list.reduce((s, m) => s + (m.calories || 0), 0)} kcal
                            </span>
                          </div>
                          {list.map((m) => (
                            <div
                              key={m.id}
                              className="rounded-xl border border-orange-100 bg-orange-50/30 p-3"
                            >
                              {editingId === m.id ? (
                                <div className="space-y-2">
                                  <MealFormFields
                                    mealType={editMealType}
                                    setMealType={setEditMealType}
                                    food={editFood}
                                    setFood={setEditFood}
                                    portion={editPortion}
                                    setPortion={setEditPortion}
                                    calories={editCalories}
                                    setCalories={setEditCalories}
                                    protein={editProtein}
                                    setProtein={setEditProtein}
                                    carbs={editCarbs}
                                    setCarbs={setEditCarbs}
                                    fat={editFat}
                                    setFat={setEditFat}
                                    note={editNote}
                                    setNote={setEditNote}
                                  />
                                  <div className="flex gap-2">
                                    <Button
                                      size="sm"
                                      className="h-7 text-xs"
                                      onClick={() => saveEdit(m.id)}
                                      disabled={saving}
                                    >
                                      {saving ? "保存中..." : "保存"}
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      className="h-7 text-xs"
                                      onClick={() => setEditingId(null)}
                                    >
                                      取消
                                    </Button>
                                  </div>
                                </div>
                              ) : (
                                <div className="flex items-start justify-between gap-3">
                                  <div className="min-w-0 flex-1">
                                    <div className="flex items-center gap-2">
                                      <p className="font-medium text-orange-950">
                                        {m.food_name}
                                      </p>
                                      {m.calories > 0 && (
                                        <span className="text-xs font-medium text-orange-600">
                                          {m.calories} kcal
                                        </span>
                                      )}
                                    </div>
                                    {m.portion && (
                                      <p className="mt-0.5 text-xs text-orange-600/60">
                                        份量：{m.portion}
                                      </p>
                                    )}
                                    {(m.protein_g != null ||
                                      m.carbs_g != null ||
                                      m.fat_g != null) && (
                                      <div className="mt-1 flex flex-wrap gap-3 text-xs text-orange-600/70">
                                        {m.protein_g != null && (
                                          <span>蛋白质 {m.protein_g}g</span>
                                        )}
                                        {m.carbs_g != null && (
                                          <span>碳水 {m.carbs_g}g</span>
                                        )}
                                        {m.fat_g != null && <span>脂肪 {m.fat_g}g</span>}
                                      </div>
                                    )}
                                    {m.note && (
                                      <p className="mt-1 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
                                        {m.note}
                                      </p>
                                    )}
                                  </div>
                                  <div className="flex shrink-0 gap-1">
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="size-7 text-orange-300 hover:text-orange-600"
                                      onClick={() => startEdit(m)}
                                    >
                                      <Pencil className="size-3.5" />
                                    </Button>
                                    <Button
                                      variant="ghost"
                                      size="icon"
                                      className="size-7 text-red-300 hover:text-red-600"
                                      onClick={() => deleteMeal(m.id)}
                                    >
                                      <Trash2 className="size-3.5" />
                                    </Button>
                                  </div>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      );
                    })
                  )}

                  {adding && (
                    <div className="flex items-center gap-1 text-xs text-orange-500/60">
                      <Check className="size-3" />
                      填写食物名称与营养数据后点击「添加」，热量将自动计入当日概览
                    </div>
                  )}
                </CardContent>
              </Card>
            </>
          )}
      <Dialog open={importDialogOpen} onOpenChange={setImportDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>从饮食计划导入</DialogTitle>
            <DialogDescription>
              {format(selectedDate, "M月d日", { locale: zhCN })} 的计划餐食，勾选后导入
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-64 space-y-2 overflow-y-auto">
            {planMeals.length === 0 ? (
              <p className="py-6 text-center text-sm text-orange-600/50">
                当天无计划餐食
              </p>
            ) : (
              planMeals.map((m) => (
                <label
                  key={m.id}
                  className="flex cursor-pointer items-center gap-3 rounded-lg border border-orange-100 p-2.5 hover:bg-orange-50/50"
                >
                  <input
                    type="checkbox"
                    checked={selectedImportIds.has(m.id)}
                    onChange={() => toggleImportMeal(m.id)}
                    className="size-4 accent-orange-500"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <Badge
                        className={cn(
                          "rounded-md px-1.5 py-0 text-[10px]",
                          mealTypeColors[m.meal_type] ?? "bg-gray-100 text-gray-600",
                        )}
                      >
                        {mealTypeLabels[m.meal_type] ?? m.meal_type}
                      </Badge>
                      <span className="truncate text-sm font-medium text-orange-950">
                        {m.food_name}
                      </span>
                    </div>
                    <span className="text-xs text-orange-600/60">
                      {m.calories ?? 0} kcal
                      {m.protein_g != null && ` · 蛋白质 ${m.protein_g}g`}
                    </span>
                  </div>
                </label>
              ))
            )}
          </div>
          <DialogFooter>
            <Button variant="ghost" size="sm" onClick={() => setImportDialogOpen(false)}>
              取消
            </Button>
            <Button
              size="sm"
              onClick={confirmImport}
              disabled={importing || selectedImportIds.size === 0}
            >
              {importing ? "导入中..." : `确认导入 (${selectedImportIds.size})`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
