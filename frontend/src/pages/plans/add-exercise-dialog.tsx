import { useState } from "react";
import { Check, Loader2, Minus, PenLine, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { showError } from "@/lib/toast";
import type { Exercise } from "@/types/exercise";
import { ExerciseSearchInline } from "./exercise-search";
import type { PlanDay, PlanDetail } from "./types";

function NumberStepper({
  value,
  onChange,
  min,
  max,
  suffix,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  suffix: string;
}) {
  const btnCls =
    "flex size-8 shrink-0 items-center justify-center rounded-lg border border-emerald-200 bg-white text-emerald-600 transition-all hover:border-emerald-400 hover:bg-emerald-50 active:scale-90 disabled:pointer-events-none disabled:opacity-30";
  return (
    <div className="flex items-center gap-1.5">
      <button
        type="button"
        className={btnCls}
        disabled={value <= min}
        onClick={() => onChange(Math.max(min, value - 1))}
      >
        <Minus className="size-3.5" />
      </button>
      <div className="flex h-9 min-w-16 flex-col items-center justify-center rounded-lg border border-emerald-100 bg-emerald-50/50 px-2">
        <span className="text-sm font-bold tabular-nums text-emerald-900">{value}</span>
        <span className="text-[10px] leading-none text-emerald-500/70">{suffix}</span>
      </div>
      <button
        type="button"
        className={btnCls}
        disabled={value >= max}
        onClick={() => onChange(Math.min(max, value + 1))}
      >
        <Plus className="size-3.5" />
      </button>
    </div>
  );
}

export function AddExerciseDialog({
  day,
  open,
  onClose,
  onPlanUpdated,
}: {
  day: PlanDay;
  open: boolean;
  onClose: () => void;
  onPlanUpdated: (plan: PlanDetail) => void;
}) {
  const [tab, setTab] = useState<"search" | "custom">("search");
  const [name, setName] = useState("");
  const [sets, setSets] = useState(3);
  const [reps, setReps] = useState(12);
  const [weight, setWeight] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setName("");
    setSets(3);
    setReps(12);
    setWeight("");
    setNotes("");
    setSaving(false);
  };

  const close = () => {
    onClose();
    setTimeout(reset, 150);
  };

  const addFromLibrary = async (ex: Exercise) => {
    try {
      const updated = await api.post<PlanDetail>(`/plans/days/${day.id}/exercises`, {
        exercise_id: ex.id,
        sets: 3,
        reps: 12,
        weight_kg: null,
        sort_order: day.exercises.length,
        notes: null,
      });
      onPlanUpdated(updated);
      close();
    } catch (e) {
      showError((e as Error).message);
    }
  };

  const addCustom = async () => {
    const trimmed = name.trim();
    if (!trimmed || saving) return;
    if (weight && parseFloat(weight) < 0) {
      showError("重量不能为负数");
      return;
    }
    setSaving(true);
    try {
      const updated = await api.post<PlanDetail>(`/plans/days/${day.id}/exercises`, {
        custom_name: trimmed,
        sets,
        reps,
        weight_kg: weight ? parseFloat(weight) : null,
        sort_order: day.exercises.length,
        notes: notes.trim() || null,
      });
      onPlanUpdated(updated);
      close();
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const tabBtn = (active: boolean) =>
    cn(
      "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-all duration-200",
      active
        ? "bg-white text-emerald-700 shadow-sm shadow-emerald-100"
        : "text-emerald-500/70 hover:text-emerald-700"
    );

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) close();
      }}
    >
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-950">
            <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-600 text-white">
              <Plus className="size-4" />
            </span>
            添加动作
          </DialogTitle>
        </DialogHeader>

        <div className="flex rounded-xl border border-emerald-100 bg-emerald-50/60 p-1">
          <button type="button" className={tabBtn(tab === "search")} onClick={() => setTab("search")}>
            <Search className="size-3.5" />
            搜索动作库
          </button>
          <button type="button" className={tabBtn(tab === "custom")} onClick={() => setTab("custom")}>
            <PenLine className="size-3.5" />
            自定义动作
          </button>
        </div>

        {tab === "search" ? (
          <div>
            <ExerciseSearchInline onPick={addFromLibrary} />
            <p className="px-1 text-[11px] text-emerald-500/60">
              点击动作即以 3 组 × 12 次 添加，添加后可在列表中调整
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-emerald-700">动作名称</label>
              <Input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addCustom();
                  }
                }}
                placeholder="如：保加利亚分腿蹲、弹力带面拉…"
                className="h-10 rounded-xl border-emerald-200 bg-white/70"
              />
            </div>

            <div className="flex flex-wrap items-end gap-4">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-emerald-700">组数</label>
                <NumberStepper value={sets} onChange={setSets} min={1} max={20} suffix="组" />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-emerald-700">次数</label>
                <NumberStepper value={reps} onChange={setReps} min={1} max={100} suffix="次" />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-emerald-700">重量（可选）</label>
                <div className="relative">
                  <Input
                    type="number"
                    min={0}
                    step={0.5}
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                    placeholder="0.0"
                    className="h-9 w-24 rounded-lg border-emerald-200 bg-white/70 pr-9 text-sm"
                  />
                  <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-emerald-400">
                    kg
                  </span>
                </div>
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-emerald-700">要点 / 备注（可选）</label>
              <Textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="如：全程核心收紧，下放 2 秒"
                className="min-h-16 resize-none rounded-xl border-emerald-200 bg-white/70 text-sm"
              />
            </div>

            <Button
              onClick={addCustom}
              disabled={!name.trim() || saving}
              className="w-full gap-1.5 bg-emerald-600 text-white transition-all hover:bg-emerald-500 active:scale-[0.99]"
            >
              {saving ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Check className="size-4" />
              )}
              添加到训练日
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
