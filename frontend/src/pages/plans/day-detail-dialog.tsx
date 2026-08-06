import { useState } from "react";
import { MetadataEditor, MetadataPreview } from "@/components/metadata-editor";
import { toMetaRows, toMetaDict, type MetaRow } from "@/lib/meta-utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Trash2, Pencil, ExternalLink, Loader2, Plus } from "lucide-react";
import { api } from "@/lib/api";
import { showError } from "@/lib/toast";
import { muscleGroupLabels, equipmentLabels, exerciseDescription } from "@/lib/exercise-labels";
import { useLanguage } from "@/lib/language-context";
import { AddExerciseDialog } from "./add-exercise-dialog";
import { dayNames, type PlanDay, type PlanDetail, type PlanExercise } from "./types";

export function DayDetailDialog({
  day,
  open,
  initialEditingExerciseId = null,
  onClose,
  onPlanUpdated,
}: {
  day: PlanDay | null;
  open: boolean;
  initialEditingExerciseId?: string | null;
  onClose: () => void;
  onPlanUpdated: (plan: PlanDetail) => void;
}) {
  const { isZh } = useLanguage();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editType, setEditType] = useState<"strength" | "cardio">("strength");
  const [editSets, setEditSets] = useState(3);
  const [editReps, setEditReps] = useState(12);
  const [editWeight, setEditWeight] = useState("");
  const [editDuration, setEditDuration] = useState("");
  const [editDistance, setEditDistance] = useState("");
  const [editCalPerMin, setEditCalPerMin] = useState("");
  const [editNotes, setEditNotes] = useState("");
  const [editMetadata, setEditMetadata] = useState<MetaRow[]>([]);
  const [saving, setSaving] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const [dayInfoSync, setDayInfoSync] = useState<string | null>(null);
  const [dayFocus, setDayFocus] = useState("");
  const [dayRest, setDayRest] = useState(60);
  const [dayMeta, setDayMeta] = useState<MetaRow[]>([]);
  const [dayInfoSaving, setDayInfoSaving] = useState(false);
  const [addDialogOpen, setAddDialogOpen] = useState(false);

  if (!open && dayInfoSync !== null) {
    setDayInfoSync(null);
  }

  if (open && day && day.id !== dayInfoSync) {
    setDayInfoSync(day.id);
    setDayFocus(day.focus ?? "");
    setDayRest(day.rest_seconds);
    setDayMeta(toMetaRows(day.metadata_));
    setEditingId(initialEditingExerciseId);
  }

  if (!day) return null;

  const startEdit = (ex: PlanExercise) => {
    setEditingId(ex.id);
    setEditType(ex.exercise_type === "cardio" ? "cardio" : "strength");
    setEditSets(ex.sets ?? 3);
    setEditReps(ex.reps ?? 12);
    setEditWeight(ex.weight_kg?.toString() ?? "");
    setEditDuration(ex.duration_min?.toString() ?? "");
    setEditDistance(ex.distance_km?.toString() ?? "");
    setEditCalPerMin(ex.calories_per_min?.toString() ?? "");
    setEditNotes(ex.notes ?? "");
    setEditMetadata(toMetaRows(ex.metadata_));
  };

  const saveEdit = async (exId: string) => {
    if (editType === "cardio") {
      const dur = parseInt(editDuration);
      if (!dur || dur < 1) {
        showError("有氧动作需提供时长（分钟）");
        return;
      }
      if (editDistance && parseFloat(editDistance) < 0) {
        showError("距离不能为负数");
        return;
      }
      if (editCalPerMin && parseFloat(editCalPerMin) < 0) {
        showError("每分钟消耗不能为负数");
        return;
      }
    } else {
      if (editSets < 1 || editSets > 20) {
        showError("组数需在 1-20 之间");
        return;
      }
      if (editReps < 1 || editReps > 100) {
        showError("次数需在 1-100 之间");
        return;
      }
      if (editWeight && parseFloat(editWeight) < 0) {
        showError("重量不能为负数");
        return;
      }
    }
    setSaving(true);
    try {
      const payload =
        editType === "cardio"
          ? {
              exercise_type: "cardio",
              duration_min: parseInt(editDuration),
              distance_km: editDistance ? parseFloat(editDistance) : null,
              calories_per_min: editCalPerMin ? parseFloat(editCalPerMin) : null,
              sets: null,
              reps: null,
              weight_kg: null,
              notes: editNotes.trim() ? editNotes.trim() : null,
              metadata_: toMetaDict(editMetadata),
            }
          : {
              exercise_type: "strength",
              sets: editSets,
              reps: editReps,
              weight_kg: editWeight ? parseFloat(editWeight) : null,
              duration_min: null,
              distance_km: null,
              calories_per_min: null,
              notes: editNotes.trim() ? editNotes.trim() : null,
              metadata_: toMetaDict(editMetadata),
            };
      const updated = await api.put<PlanDetail>(`/plans/exercises/${exId}`, payload);
      setEditingId(null);
      onPlanUpdated(updated);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const deleteExercise = async (exId: string) => {
    if (!confirm("确定删除该动作？")) return;
    setDeletingId(exId);
    try {
      const updated = await api.delete<PlanDetail>(`/plans/exercises/${exId}`);
      onPlanUpdated(updated);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setDeletingId(null);
    }
  };

  const saveDayInfo = async () => {
    if (dayRest < 0) {
      showError("组间休息不能为负数");
      return;
    }
    setDayInfoSaving(true);
    try {
      const updated = await api.put<PlanDetail>(`/plans/days/${day.id}`, {
        focus: dayFocus.trim() || null,
        rest_seconds: dayRest,
        metadata_: toMetaDict(dayMeta),
      });
      onPlanUpdated(updated);
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setDayInfoSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="plan-day-dialog max-h-[85vh] overflow-y-auto sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-950">
            <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
              {dayNames[day.day_of_week - 1]}
            </span>
            {day.focus || "综合训练"}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3 min-w-0">
          <div className="space-y-2 rounded-lg border border-emerald-100 bg-emerald-50/40 p-3">
            <div className="flex items-center gap-2">
              <span className="w-16 shrink-0 text-xs font-medium text-emerald-700">训练重点</span>
              <Input
                value={dayFocus}
                onChange={(e) => setDayFocus(e.target.value)}
                placeholder="如 胸部 + 三头"
                className="h-8 text-sm"
              />
            </div>
            <div className="flex items-center gap-2">
              <span className="w-16 shrink-0 text-xs font-medium text-emerald-700">组间休息</span>
              <Input
                type="number"
                min={0}
                value={dayRest}
                onChange={(e) => setDayRest(parseInt(e.target.value) || 0)}
                className="h-8 w-24 text-sm"
              />
              <span className="text-xs text-emerald-600">秒</span>
            </div>
            <div>
              <p className="mb-1 text-xs font-medium text-emerald-700">自定义项（可选）</p>
              <MetadataEditor value={dayMeta} onChange={setDayMeta} />
            </div>
            <div className="flex justify-end">
              <Button size="sm" className="h-7 text-xs" onClick={saveDayInfo} disabled={dayInfoSaving}>
                {dayInfoSaving ? "保存中..." : "保存训练日信息"}
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <p className="text-xs font-medium text-emerald-700">
              当日动作（{day.exercises.length}）
            </p>
            <Button
              size="sm"
              onClick={() => setAddDialogOpen(true)}
              className="h-7 gap-1 rounded-lg bg-emerald-600 px-2.5 text-xs text-white shadow-sm shadow-emerald-200 transition-all hover:bg-emerald-500 active:scale-95"
            >
              <Plus className="size-3.5" />
              添加动作
            </Button>
          </div>
          {day.exercises.length === 0 ? (
            <p className="py-4 text-center text-sm text-emerald-600/50">暂无动作，点击上方「添加动作」开始</p>
          ) : (
            <div className="space-y-2">
              {[...day.exercises]
                .sort((a, b) => a.sort_order - b.sort_order)
                .map((ex, idx) => (
                  <div
                    key={ex.id}
                    className="rounded-lg border border-emerald-100 bg-emerald-50/50 px-4 py-3"
                  >
                    {editingId === ex.id ? (
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-medium text-emerald-900">{ex.exercise_name ?? "未知动作"}</p>
                          <div className="flex rounded-lg border border-emerald-100 bg-emerald-50/60 p-0.5">
                            {(["strength", "cardio"] as const).map((t) => (
                              <button
                                key={t}
                                type="button"
                                onClick={() => setEditType(t)}
                                className={
                                  editType === t
                                    ? "rounded-md bg-white px-2.5 py-1 text-xs font-semibold text-emerald-700 shadow-sm"
                                    : "rounded-md px-2.5 py-1 text-xs text-emerald-500/70 hover:text-emerald-700"
                                }
                              >
                                {t === "strength" ? "力量" : "有氧"}
                              </button>
                            ))}
                          </div>
                        </div>
                        {editType === "cardio" ? (
                          <div className="flex items-center gap-2">
                            <div className="flex items-center gap-1">
                              <Input
                                type="number"
                                min={1}
                                placeholder="时长"
                                value={editDuration}
                                onChange={(e) => setEditDuration(e.target.value)}
                                className="w-20 h-8 text-sm"
                              />
                              <span className="text-xs text-emerald-600">分钟</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <Input
                                type="number"
                                min={0}
                                step={0.1}
                                placeholder="距离（可选）"
                                value={editDistance}
                                onChange={(e) => setEditDistance(e.target.value)}
                                className="w-24 h-8 text-sm"
                              />
                              <span className="text-xs text-emerald-600">km</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <Input
                                type="number"
                                min={0}
                                step={0.1}
                                placeholder="消耗（可选）"
                                value={editCalPerMin}
                                onChange={(e) => setEditCalPerMin(e.target.value)}
                                className="w-24 h-8 text-sm"
                              />
                              <span className="text-xs text-emerald-600">kcal/分钟</span>
                            </div>
                          </div>
                        ) : (
                          <div className="flex items-center gap-2">
                            <div className="flex items-center gap-1">
                              <Input
                                type="number"
                                min={1}
                                max={20}
                                value={editSets}
                                onChange={(e) => setEditSets(parseInt(e.target.value) || 1)}
                                className="w-16 h-8 text-sm"
                              />
                              <span className="text-xs text-emerald-600">组</span>
                            </div>
                            <span className="text-emerald-400">×</span>
                            <div className="flex items-center gap-1">
                              <Input
                                type="number"
                                min={1}
                                max={100}
                                value={editReps}
                                onChange={(e) => setEditReps(parseInt(e.target.value) || 1)}
                                className="w-16 h-8 text-sm"
                              />
                              <span className="text-xs text-emerald-600">次</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <Input
                                type="number"
                                min={0}
                                step={0.5}
                                placeholder="重量"
                                value={editWeight}
                                onChange={(e) => setEditWeight(e.target.value)}
                                className="w-20 h-8 text-sm"
                              />
                              <span className="text-xs text-emerald-600">kg</span>
                            </div>
                          </div>
                        )}
                        <Textarea
                          value={editNotes}
                          onChange={(e) => setEditNotes(e.target.value)}
                          placeholder="动作要点 / 备注（如：腰背挺直，下放吸气）"
                          className="min-h-16 resize-none text-sm"
                        />
                        <MetadataEditor
                          value={editMetadata}
                          onChange={setEditMetadata}
                        />
                        <div className="flex gap-2">
                          <Button size="sm" className="h-7 text-xs" onClick={() => saveEdit(ex.id)} disabled={saving}>
                            {saving ? "保存中..." : "保存"}
                          </Button>
                          <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setEditingId(null)}>
                            取消
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div
                        className="flex cursor-pointer items-start gap-3 transition-colors hover:border-emerald-300"
                        title="点击编辑该动作"
                        onClick={() => startEdit(ex)}
                      >
                        <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-emerald-200 text-xs font-bold text-emerald-700">
                          {idx + 1}
                        </span>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-1.5">
                            <p className="font-medium text-emerald-900">
                              {ex.exercise?.name ?? ex.exercise_name ?? "未知动作"}
                            </p>
                            {!ex.exercise_id && (
                              <Badge
                                variant="outline"
                                className="h-5 border-violet-200 bg-violet-50 px-1.5 text-[10px] text-violet-600"
                              >
                                自定义
                              </Badge>
                            )}
                            {ex.exercise_type === "cardio" && (
                              <Badge
                                variant="outline"
                                className="h-5 border-sky-200 bg-sky-50 px-1.5 text-[10px] text-sky-600"
                              >
                                有氧
                              </Badge>
                            )}
                            {ex.exercise?.muscle_group && (
                              <Badge
                                variant="outline"
                                className="h-5 border-emerald-200 px-1.5 text-[10px] text-emerald-600"
                              >
                                {muscleGroupLabels[ex.exercise.muscle_group] ?? ex.exercise.muscle_group}
                              </Badge>
                            )}
                            {ex.exercise?.equipment && (
                              <Badge
                                variant="outline"
                                className="h-5 border-sky-200 bg-sky-50 px-1.5 text-[10px] text-sky-600"
                              >
                                {equipmentLabels[ex.exercise.equipment] ?? ex.exercise.equipment}
                              </Badge>
                            )}
                          </div>
                          <p className="mt-0.5 text-xs text-emerald-600/70">
                            {ex.exercise_type === "cardio" ? (
                              <span className="font-medium text-emerald-700">
                                {ex.duration_min ?? 0} 分钟
                                {ex.distance_km ? ` · ${ex.distance_km} km` : ""}
                                {ex.calories_per_min ? ` · ${ex.calories_per_min} kcal/分钟` : ""}
                              </span>
                            ) : (
                              <>
                                <span className="font-medium text-emerald-700">
                                  {ex.sets ?? "-"} 组 × {ex.reps ?? "-"} 次
                                </span>
                                {ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}
                              </>
                            )}
                          </p>
                          {ex.exercise && exerciseDescription(ex.exercise, isZh) && (
                            <p className="mt-1 line-clamp-2 text-xs text-emerald-600/60">
                              {exerciseDescription(ex.exercise, isZh)}
                            </p>
                          )}
                          {ex.notes && (
                            <p className="mt-1 rounded bg-amber-50 px-2 py-1 text-xs text-amber-700">
                              <span className="font-medium">要点：</span>
                              {ex.notes}
                            </p>
                          )}
                          <div className="mt-1">
                            <MetadataPreview value={ex.metadata_} />
                          </div>
                        </div>
                        <div className="flex shrink-0 flex-col gap-1">
                          {ex.exercise_id && (
                            <a
                              href={`/exercises/${ex.exercise_id}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="查看动作详情"
                              className="flex size-7 items-center justify-center rounded-md text-emerald-400 hover:bg-emerald-50 hover:text-emerald-600"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <ExternalLink className="size-3.5" />
                            </a>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7 text-emerald-400 hover:text-emerald-600"
                            onClick={(e) => {
                              e.stopPropagation();
                              startEdit(ex);
                            }}
                          >
                            <Pencil className="size-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="size-7 text-red-300 hover:text-red-600"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteExercise(ex.id);
                            }}
                            disabled={deletingId === ex.id}
                          >
                            {deletingId === ex.id ? (
                              <Loader2 className="size-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="size-3.5" />
                            )}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            关闭
          </Button>
        </DialogFooter>
      </DialogContent>

      <AddExerciseDialog
        day={day}
        open={addDialogOpen}
        onClose={() => setAddDialogOpen(false)}
        onPlanUpdated={onPlanUpdated}
      />
    </Dialog>
  );
}
