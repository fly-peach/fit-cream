import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Loader2, Shuffle } from "lucide-react";
import { api } from "@/lib/api";
import { showError, showSuccess } from "@/lib/toast";
import { ExerciseSearchInline } from "./exercise-search";
import type { Exercise } from "@/types/exercise";
import type { PlanDetail } from "./types";

export function SwapExerciseDialog({
  planExerciseId,
  open,
  onClose,
  onPlanUpdated,
}: {
  planExerciseId: string | null;
  open: boolean;
  onClose: () => void;
  onPlanUpdated: (plan: PlanDetail) => void;
}) {
  const [swapping, setSwapping] = useState<string | null>(null);

  const handlePick = async (ex: Exercise) => {
    if (!planExerciseId) return;
    setSwapping(ex.id);
    try {
      const updated = await api.put<PlanDetail>(`/plans/exercises/${planExerciseId}`, {
        exercise_id: ex.id,
      });
      onPlanUpdated(updated);
      showSuccess(`已更换为「${ex.name}」`);
      onClose();
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setSwapping(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-950">
            <span className="flex size-7 items-center justify-center rounded-lg bg-emerald-600 text-white">
              <Shuffle className="size-4" />
            </span>
            更换动作
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-2">
          <ExerciseSearchInline onPick={handlePick} />
          {swapping && (
            <div className="flex items-center gap-1.5 text-xs text-emerald-600">
              <Loader2 className="size-3.5 animate-spin" />
              更换中...
            </div>
          )}
          <p className="px-1 text-[11px] text-emerald-500/60">
            选择新动作后，原动作的组数、次数、重量等参数将保留
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}
