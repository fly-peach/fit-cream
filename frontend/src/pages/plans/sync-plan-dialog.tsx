import { useMemo, useState } from "react";
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
  isSameDay,
  addMonths,
  subMonths,
  startOfWeek,
  endOfWeek,
  isToday,
} from "date-fns";
import { zhCN } from "date-fns/locale";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { ChevronLeft, ChevronRight, Loader2, RefreshCw } from "lucide-react";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { showError, showSuccess } from "@/lib/toast";
import { dayNames, parseDateLocal, dateToDow, type PlanDetail } from "./types";

const todayStr = format(new Date(), "yyyy-MM-dd");

export function SyncPlanDialog({
  activePlan,
  targetDayOfWeek,
  open,
  onClose,
  onPlanUpdated,
}: {
  activePlan: PlanDetail | null;
  targetDayOfWeek: number;
  open: boolean;
  onClose: () => void;
  onPlanUpdated: (plan: PlanDetail) => void;
}) {
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const [selectedDateStr, setSelectedDateStr] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const selectedDate = selectedDateStr ? parseDateLocal(selectedDateStr) : null;
  const sourceDow = selectedDate ? dateToDow(selectedDate) : null;
  const sourceDay = !activePlan || !sourceDow
    ? null
    : activePlan.days.find((d) => d.day_of_week === sourceDow) ?? null;

  const calendarDays = useMemo(() => {
    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
    const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
    return eachDayOfInterval({ start: calStart, end: calEnd });
  }, [currentMonth]);

  const doSync = async () => {
    if (!activePlan || !sourceDow || !sourceDay) return;
    setSyncing(true);
    try {
      const updated = await api.post<PlanDetail>(`/plans/${activePlan.id}/copy-day`, {
        source_day_of_week: sourceDow,
        target_day_of_week: targetDayOfWeek,
      });
      onPlanUpdated(updated);
      showSuccess(`已把${dayNames[sourceDow - 1]}训练同步到${dayNames[targetDayOfWeek - 1]}`);
      onClose();
    } catch (e) {
      showError((e as Error).message);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-950">
            <RefreshCw className="size-4 text-emerald-500" />
            同步计划
          </DialogTitle>
        </DialogHeader>

        <p className="text-sm text-emerald-600/70">
          选择源日期，预览该日期的训练内容，确认后同步到
          <span className="font-semibold text-emerald-700">{dayNames[targetDayOfWeek - 1]}</span>
          （会将{dayNames[targetDayOfWeek - 1]}的训练内容替换为所选日期的内容）。
        </p>

        <div className="grid gap-4 sm:grid-cols-2">
          <div className="rounded-lg border border-emerald-100 bg-emerald-50/40 p-3">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-medium text-emerald-900">
                {selectedDate ? format(selectedDate, "yyyy年M月d日", { locale: zhCN }) : "选择日期"}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 text-emerald-700 hover:bg-emerald-100"
                  onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
                >
                  <ChevronLeft className="size-4" />
                </Button>
                <span className="min-w-20 text-center text-sm font-medium text-emerald-900">
                  {format(currentMonth, "yyyy年M月", { locale: zhCN })}
                </span>
                <Button
                  variant="ghost"
                  size="icon"
                  className="size-7 text-emerald-700 hover:bg-emerald-100"
                  onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
                >
                  <ChevronRight className="size-4" />
                </Button>
              </div>
            </div>
            <div className="mb-1 grid grid-cols-7 text-center text-xs font-medium text-emerald-600/60">
              {["一", "二", "三", "四", "五", "六", "日"].map((d) => (
                <div key={d} className="py-1">
                  {d}
                </div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-1">
              {calendarDays.map((day) => {
                const dateStr = format(day, "yyyy-MM-dd");
                const inMonth = isSameMonth(day, currentMonth);
                const isSelected = isSameDay(day, selectedDate ?? new Date(todayStr));
                return (
                  <button
                    key={dateStr}
                    type="button"
                    onClick={() => setSelectedDateStr(dateStr)}
                    className={cn(
                      "relative flex size-9 items-center justify-center rounded-lg text-sm transition-all duration-150",
                      !inMonth && "text-emerald-200",
                      inMonth && !isSelected && "text-emerald-800 hover:bg-emerald-100",
                      isSelected && "bg-emerald-600 text-white shadow-sm",
                      isToday(day) && inMonth && !isSelected && "font-bold",
                    )}
                  >
                    {format(day, "d")}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="flex flex-col rounded-lg border border-emerald-100 bg-white p-3">
            <p className="mb-2 flex items-center gap-1.5 text-sm font-medium text-emerald-900">
              <RefreshCw className="size-3.5 text-emerald-500" />
              源日期训练内容
            </p>
            {!selectedDate ? (
              <p className="py-6 text-center text-xs text-emerald-500/60">请先在左侧选择日期</p>
            ) : !sourceDay ? (
              <p className="py-6 text-center text-xs text-emerald-500/60">
                {dayNames[sourceDow! - 1]}没有训练安排，无法同步
              </p>
            ) : (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="flex size-6 items-center justify-center rounded-lg bg-emerald-600 text-xs font-bold text-white">
                    {dayNames[sourceDay.day_of_week - 1]}
                  </span>
                  <span className="text-sm font-medium text-emerald-900">
                    {sourceDay.focus || "综合训练"}
                  </span>
                </div>
                {sourceDay.exercises.length === 0 ? (
                  <p className="text-xs text-emerald-500/60">该训练日暂无动作</p>
                ) : (
                  <div className="space-y-1.5">
                    {[...sourceDay.exercises]
                      .sort((a, b) => a.sort_order - b.sort_order)
                      .map((ex) => (
                        <div
                          key={ex.id}
                          className="flex items-center justify-between gap-2 rounded-lg bg-emerald-50/50 px-3 py-2 text-sm"
                        >
                          <span className="truncate font-medium text-emerald-900">
                            {ex.exercise_name ?? "未知动作"}
                          </span>
                          <span className="shrink-0 tabular-nums text-emerald-600/70">
                            {ex.exercise_type === "cardio"
                              ? `${ex.duration_min ?? 0} 分钟${ex.distance_km ? ` · ${ex.distance_km}km` : ""}`
                              : `${ex.sets ?? "-"} 组 × ${ex.reps ?? "-"} 次${ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}`}
                          </span>
                        </div>
                      ))}
                  </div>
                )}
                <Badge className="border-emerald-200 bg-emerald-50 text-emerald-700">
                  {sourceDay.exercises.length} 个动作
                </Badge>
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={onClose} disabled={syncing}>
            取消
          </Button>
          <Button
            className="bg-emerald-600 text-white hover:bg-emerald-700"
            onClick={doSync}
            disabled={!sourceDay || syncing}
          >
            {syncing ? (
              <Loader2 className="mr-1 size-4 animate-spin" />
            ) : (
              <RefreshCw className="mr-1 size-4" />
            )}
            同步到{dayNames[targetDayOfWeek - 1]}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}