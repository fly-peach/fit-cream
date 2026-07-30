import { useState } from "react";
import { MetadataEditor, MetadataPreview } from "@/components/metadata-editor";
import { toMetaRows, toMetaDict, type MetaRow } from "@/lib/meta-utils";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Loader2, Trash2, UtensilsCrossed, Pencil, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { dayNames, mealTypeLabels, mealTypeColors, type DietDay, type DietMeal, type DietPlanDetail } from "./types";

export function DietPlanCard({
  dietPlan,
  dayOfWeek,
  selectedDateLabel,
  onUpdated,
}: {
  dietPlan: DietPlanDetail | null;
  dayOfWeek: number;
  selectedDateLabel: string;
  onUpdated: () => void;
}) {
  const [editingMealId, setEditingMealId] = useState<string | null>(null);
  const [editFood, setEditFood] = useState("");
  const [editCalories, setEditCalories] = useState("");
  const [editProtein, setEditProtein] = useState("");
  const [editCarbs, setEditCarbs] = useState("");
  const [editFat, setEditFat] = useState("");
  const [editPortion, setEditPortion] = useState("");
  const [editMealMetadata, setEditMealMetadata] = useState<MetaRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [editingDayId, setEditingDayId] = useState<string | null>(null);
  const [editDayFocus, setEditDayFocus] = useState("");
  const [editDayMetadata, setEditDayMetadata] = useState<MetaRow[]>([]);

  const [addingMeal, setAddingMeal] = useState(false);
  const [newMealType, setNewMealType] = useState<string>("breakfast");
  const [newFood, setNewFood] = useState("");
  const [newCalories, setNewCalories] = useState("");
  const [newProtein, setNewProtein] = useState("");
  const [newCarbs, setNewCarbs] = useState("");
  const [newFat, setNewFat] = useState("");
  const [newPortion, setNewPortion] = useState("");
  const [newMealMetadata, setNewMealMetadata] = useState<MetaRow[]>([]);
  const [addSaving, setAddSaving] = useState(false);
  const [dayAddSaving, setDayAddSaving] = useState(false);
  const [planCreating, setPlanCreating] = useState(false);

  const createDietPlan = async () => {
    setPlanCreating(true);
    try {
      await api.post("/diet-plans", {
        name: "我的饮食计划",
        target_calories: null,
        goal: null,
        days: [],
      });
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setPlanCreating(false);
    }
  };

  if (!dietPlan) {
    return (
      <Card className="flex h-full min-h-64 items-center justify-center border-dashed border-orange-200">
        <CardContent className="flex flex-col items-center gap-3 text-center">
          <UtensilsCrossed className="size-8 text-orange-300" />
          <p className="text-sm text-orange-600/60">
            暂无饮食计划，可手动创建或让 AI 教练为你定制
          </p>
          <Button
            variant="outline"
            size="sm"
            className="border-orange-200 text-orange-700"
            onClick={createDietPlan}
            disabled={planCreating}
          >
            {planCreating ? (
              <Loader2 className="mr-1 size-4 animate-spin" />
            ) : (
              <Plus className="mr-1 size-4" />
            )}
            创建饮食计划
          </Button>
        </CardContent>
      </Card>
    );
  }

  const currentDay = dietPlan.days.find((d) => d.day_of_week === dayOfWeek);
  const totalCalories = currentDay?.meals.reduce((sum, m) => sum + (m.calories ?? 0), 0) ?? 0;

  const startEditMeal = (meal: DietMeal) => {
    setEditingMealId(meal.id);
    setEditFood(meal.food_name);
    setEditCalories(meal.calories?.toString() ?? "");
    setEditProtein(meal.protein_g?.toString() ?? "");
    setEditCarbs(meal.carbs_g?.toString() ?? "");
    setEditFat(meal.fat_g?.toString() ?? "");
    setEditPortion(meal.portion ?? "");
    setEditMealMetadata(toMetaRows(meal.metadata_));
  };

  const saveMealEdit = async (mealId: string) => {
    setSaving(true);
    try {
      await api.put(`/diet-plans/meals/${mealId}`, {
        food_name: editFood,
        calories: editCalories ? parseInt(editCalories) : null,
        protein_g: editProtein ? parseFloat(editProtein) : null,
        carbs_g: editCarbs ? parseFloat(editCarbs) : null,
        fat_g: editFat ? parseFloat(editFat) : null,
        portion: editPortion || null,
        metadata_: toMetaDict(editMealMetadata),
      });
      setEditingMealId(null);
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const deleteMeal = async (mealId: string) => {
    if (!confirm("确定删除该餐食？")) return;
    try {
      await api.delete(`/diet-plans/meals/${mealId}`);
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    }
  };

  const startEditDay = (day: DietDay) => {
    setEditingDayId(day.id);
    setEditDayFocus(day.focus ?? "");
    setEditDayMetadata(toMetaRows(day.metadata_));
  };

  const saveDayEdit = async (dayId: string) => {
    setSaving(true);
    try {
      await api.put(`/diet-plans/days/${dayId}`, {
        focus: editDayFocus.trim() || null,
        metadata_: toMetaDict(editDayMetadata),
      });
      setEditingDayId(null);
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const resetAddMealForm = () => {
    setNewMealType("breakfast");
    setNewFood("");
    setNewCalories("");
    setNewProtein("");
    setNewCarbs("");
    setNewFat("");
    setNewPortion("");
    setNewMealMetadata([]);
  };

  const addMeal = async () => {
    if (!currentDay) return;
    if (!newFood.trim()) {
      alert("请填写食物名称");
      return;
    }
    setAddSaving(true);
    try {
      await api.post(`/diet-plans/days/${currentDay.id}/meals`, {
        meal_type: newMealType,
        food_name: newFood.trim(),
        calories: newCalories ? parseInt(newCalories) : null,
        protein_g: newProtein ? parseFloat(newProtein) : null,
        carbs_g: newCarbs ? parseFloat(newCarbs) : null,
        fat_g: newFat ? parseFloat(newFat) : null,
        portion: newPortion.trim() || null,
        sort_order: currentDay.meals.length,
        metadata_: toMetaDict(newMealMetadata),
      });
      setAddingMeal(false);
      resetAddMealForm();
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setAddSaving(false);
    }
  };

  const addDietDayFor = async () => {
    if (!dietPlan?.id) return;
    setDayAddSaving(true);
    try {
      await api.post(`/diet-plans/${dietPlan.id}/days`, {
        day_of_week: dayOfWeek,
        focus: `${dayNames[dayOfWeek - 1]}饮食`,
        meals: [],
      });
      onUpdated();
    } catch (e) {
      alert((e as Error).message);
    } finally {
      setDayAddSaving(false);
    }
  };

  return (
    <Card className="border-orange-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-base font-semibold text-orange-950">
              <UtensilsCrossed className="size-4 text-orange-500" />
              当日饮食
            </CardTitle>
            <p className="mt-1 text-xs text-orange-600/70">
              {selectedDateLabel}
              {dietPlan.name ? ` · ${dietPlan.name}` : ""}
            </p>
          </div>
          {dietPlan.target_calories && (
            <Badge className="border-orange-200 bg-orange-50 text-orange-700">
              {dietPlan.target_calories} kcal/天
            </Badge>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">

        {!currentDay ? (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <p className="text-sm text-orange-600/60">
              {dayNames[dayOfWeek - 1]}暂无饮食安排
            </p>
            <Button
              variant="outline"
              size="sm"
              className="border-orange-200 text-orange-700"
              onClick={addDietDayFor}
              disabled={dayAddSaving}
            >
              {dayAddSaving ? (
                <Loader2 className="mr-1 size-4 animate-spin" />
              ) : (
                <Plus className="mr-1 size-4" />
              )}
              添加{dayNames[dayOfWeek - 1]}饮食日
            </Button>
          </div>
        ) : (
          <div className="space-y-3">
            {editingDayId === currentDay.id ? (
              <div className="space-y-2 rounded-lg border border-orange-200 bg-orange-50/50 p-2">
                <Input
                  value={editDayFocus}
                  onChange={(e) => setEditDayFocus(e.target.value)}
                  placeholder="今日饮食重点"
                  className="h-8 text-sm"
                />
                <MetadataEditor value={editDayMetadata} onChange={setEditDayMetadata} />
                <div className="flex gap-2">
                  <Button size="sm" className="h-7 text-xs" onClick={() => saveDayEdit(currentDay.id)} disabled={saving}>
                    {saving ? "保存中..." : "保存"}
                  </Button>
                  <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditingDayId(null)}>
                    取消
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-1">
                <div className="flex items-center justify-between">
                  {currentDay.focus ? (
                    <p className="text-xs font-medium text-orange-600/70">📋 {currentDay.focus}</p>
                  ) : (
                    <span />
                  )}
                  <Button
                    variant="ghost"
                    size="icon"
                    className="size-6 text-orange-300 hover:text-orange-600"
                    onClick={() => startEditDay(currentDay)}
                  >
                    <Pencil className="size-3" />
                  </Button>
                </div>
                <MetadataPreview value={currentDay.metadata_} />
              </div>
            )}
            <div className="flex items-center justify-between rounded-lg bg-orange-50 px-3 py-2">
              <span className="text-xs text-orange-600">当日总热量</span>
              <span className="text-sm font-bold text-orange-600">{totalCalories} kcal</span>
            </div>
            {currentDay.meals.length === 0 ? (
              <p className="py-4 text-center text-sm text-orange-600/50">
                暂无餐食，点击下方添加
              </p>
            ) : (
              [...currentDay.meals]
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((meal) => (
                  <div
                    key={meal.id}
                    className="rounded-xl border border-orange-100 bg-orange-50/30 p-3"
                  >
                    {editingMealId === meal.id ? (
                      <div className="space-y-2">
                        <Input
                          value={editFood}
                          onChange={(e) => setEditFood(e.target.value)}
                          placeholder="食物名称"
                          className="h-8 text-sm"
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <div className="flex items-center gap-1">
                            <Input
                              type="number"
                              value={editCalories}
                              onChange={(e) => setEditCalories(e.target.value)}
                              placeholder="卡路里"
                              className="h-7 text-xs"
                            />
                            <span className="text-[10px] text-orange-500">kcal</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Input
                              value={editPortion}
                              onChange={(e) => setEditPortion(e.target.value)}
                              placeholder="份量"
                              className="h-7 text-xs"
                            />
                          </div>
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <div className="flex items-center gap-1">
                            <Input
                              type="number"
                              step={0.1}
                              value={editProtein}
                              onChange={(e) => setEditProtein(e.target.value)}
                              placeholder="蛋白质"
                              className="h-7 text-xs"
                            />
                            <span className="text-[10px] text-orange-500">g</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Input
                              type="number"
                              step={0.1}
                              value={editCarbs}
                              onChange={(e) => setEditCarbs(e.target.value)}
                              placeholder="碳水"
                              className="h-7 text-xs"
                            />
                            <span className="text-[10px] text-orange-500">g</span>
                          </div>
                          <div className="flex items-center gap-1">
                            <Input
                              type="number"
                              step={0.1}
                              value={editFat}
                              onChange={(e) => setEditFat(e.target.value)}
                              placeholder="脂肪"
                              className="h-7 text-xs"
                            />
                            <span className="text-[10px] text-orange-500">g</span>
                          </div>
                        </div>
                        <MetadataEditor value={editMealMetadata} onChange={setEditMealMetadata} />
                        <div className="flex gap-2">
                          <Button size="sm" className="h-7 text-xs" onClick={() => saveMealEdit(meal.id)} disabled={saving}>
                            {saving ? "保存中..." : "保存"}
                          </Button>
                          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditingMealId(null)}>
                            取消
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <>
                        <div className="mb-2 flex items-center justify-between">
                          <span
                            className={cn(
                              "rounded-md px-2 py-0.5 text-xs font-medium",
                              mealTypeColors[meal.meal_type] ?? "bg-gray-100 text-gray-600"
                            )}
                          >
                            {mealTypeLabels[meal.meal_type] ?? meal.meal_type}
                          </span>
                          <div className="flex items-center gap-1">
                            {meal.calories && (
                              <span className="text-xs font-medium text-orange-600">{meal.calories} kcal</span>
                            )}
                            <Button variant="ghost" size="icon" className="size-6 text-orange-300 hover:text-orange-600" onClick={() => startEditMeal(meal)}>
                              <Pencil className="size-3" />
                            </Button>
                            <Button variant="ghost" size="icon" className="size-6 text-red-300 hover:text-red-600" onClick={() => deleteMeal(meal.id)}>
                              <Trash2 className="size-3" />
                            </Button>
                          </div>
                        </div>
                        <p className="font-medium text-orange-950">{meal.food_name}</p>
                        {meal.portion && (
                          <p className="mt-0.5 text-xs text-orange-600/60">份量：{meal.portion}</p>
                        )}
                        {(meal.protein_g || meal.carbs_g || meal.fat_g) && (
                          <div className="mt-2 flex gap-3 text-xs text-orange-600/70">
                            {meal.protein_g != null && <span>蛋白质 {meal.protein_g}g</span>}
                            {meal.carbs_g != null && <span>碳水 {meal.carbs_g}g</span>}
                            {meal.fat_g != null && <span>脂肪 {meal.fat_g}g</span>}
                          </div>
                        )}
                        <div className="mt-1">
                          <MetadataPreview value={meal.metadata_} />
                        </div>
                      </>
                    )}
                  </div>
                ))
            )}

            {addingMeal ? (
              <div className="space-y-2 rounded-lg border border-orange-200 bg-orange-50/40 p-3">
                <div className="flex flex-wrap gap-1">
                  {Object.entries(mealTypeLabels).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => setNewMealType(key)}
                      className={cn(
                        "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                        newMealType === key
                          ? mealTypeColors[key]
                          : "bg-white text-orange-600/70 hover:bg-orange-100",
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <Input
                  value={newFood}
                  onChange={(e) => setNewFood(e.target.value)}
                  placeholder="食物名称"
                  className="h-8 text-sm"
                />
                <div className="grid grid-cols-2 gap-2">
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      value={newCalories}
                      onChange={(e) => setNewCalories(e.target.value)}
                      placeholder="卡路里"
                      className="h-7 text-xs"
                    />
                    <span className="text-[10px] text-orange-500">kcal</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Input
                      value={newPortion}
                      onChange={(e) => setNewPortion(e.target.value)}
                      placeholder="份量"
                      className="h-7 text-xs"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      step={0.1}
                      value={newProtein}
                      onChange={(e) => setNewProtein(e.target.value)}
                      placeholder="蛋白质"
                      className="h-7 text-xs"
                    />
                    <span className="text-[10px] text-orange-500">g</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      step={0.1}
                      value={newCarbs}
                      onChange={(e) => setNewCarbs(e.target.value)}
                      placeholder="碳水"
                      className="h-7 text-xs"
                    />
                    <span className="text-[10px] text-orange-500">g</span>
                  </div>
                  <div className="flex items-center gap-1">
                    <Input
                      type="number"
                      step={0.1}
                      value={newFat}
                      onChange={(e) => setNewFat(e.target.value)}
                      placeholder="脂肪"
                      className="h-7 text-xs"
                    />
                    <span className="text-[10px] text-orange-500">g</span>
                  </div>
                </div>
                <MetadataEditor value={newMealMetadata} onChange={setNewMealMetadata} />
                <div className="flex gap-2">
                  <Button size="sm" className="h-7 text-xs" onClick={addMeal} disabled={addSaving}>
                    {addSaving ? "添加中..." : "添加"}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="h-7 text-xs"
                    onClick={() => {
                      setAddingMeal(false);
                      resetAddMealForm();
                    }}
                  >
                    取消
                  </Button>
                </div>
              </div>
            ) : (
              <Button
                variant="outline"
                size="sm"
                className="border-orange-200 text-orange-700"
                onClick={() => setAddingMeal(true)}
              >
                <Plus className="mr-1 size-4" />
                添加餐食
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
