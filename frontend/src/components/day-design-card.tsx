/**
 * 单日训练方案卡片
 *
 * 把 present_day_design_tool 步骤渲染为当日方案提案：
 * - 动作表格（动作 / 组次·重量 / 说明）
 * - 设计依据（rationale）
 * - 确认按钮：发结构化消息「[确认当日设计: <item_id>]」回到对话（复用 sendMessage）
 *
 * 交互态同 FormCard：仅最新助手消息且非流式时可点；提交后置灰「已确认」。
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2Icon, DumbbellIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AgentStep, DayDesign, DayExerciseDesign } from "@/types/chat";

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

function exerciseDetail(ex: DayExerciseDesign): string {
  if (ex.exercise_type === "cardio") {
    return [
      ex.duration_min ? `${ex.duration_min}分钟` : null,
      ex.distance_km ? `${ex.distance_km}km` : null,
    ]
      .filter(Boolean)
      .join(" ");
  }
  return [
    ex.sets ? `${ex.sets}组` : null,
    ex.reps ? `${ex.reps}次` : null,
    ex.weight_kg ? `${ex.weight_kg}kg` : null,
  ]
    .filter(Boolean)
    .join(" · ");
}

interface DayDesignCardProps {
  step: AgentStep;
  interactive: boolean;
  onSubmit: (text: string) => void;
}

export function DayDesignCard({ step, interactive, onSubmit }: DayDesignCardProps) {
  const input = (step.input || {}) as {
    item_id?: string;
    day_design?: DayDesign;
    rationale?: string;
  };
  const design = input.day_design;
  const [submitted, setSubmitted] = useState(false);

  if (!design) return null;

  const hasNotes = design.exercises.some((e) => e.notes);
  const topRationale = input.rationale || design.rationale;
  const canSubmit = interactive && !submitted;

  const handleConfirm = () => {
    if (!canSubmit) return;
    onSubmit(`[确认当日设计: ${input.item_id || ""}]`);
    setSubmitted(true);
  };

  return (
    <div className="my-2 overflow-hidden rounded-xl border border-emerald-200 bg-white shadow-sm">
      <div className="flex items-start gap-2.5 border-b border-emerald-100 bg-emerald-50/40 px-4 py-3">
        <DumbbellIcon className="mt-0.5 size-4 shrink-0 text-emerald-600" />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-emerald-950">
            {WEEKDAYS[design.day_of_week - 1]} · {design.focus}
            <span className="ml-1.5 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] font-normal text-emerald-700">
              {design.day_type}
            </span>
          </div>
          <div className="mt-0.5 text-xs text-emerald-700/70">当日训练方案，确认后将加入计划</div>
        </div>
        {submitted && (
          <span className="ml-auto inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">
            <CheckCircle2Icon className="size-3" />
            已确认
          </span>
        )}
      </div>

      <div className="px-4 py-3">
        <div className="overflow-x-auto rounded-lg border border-emerald-200">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-emerald-100 bg-emerald-50/30 text-left text-emerald-800/70">
                <th className="px-3 py-1.5 font-medium">动作</th>
                <th className="px-3 py-1.5 font-medium">组次 / 重量</th>
                {hasNotes ? <th className="px-3 py-1.5 font-medium">说明</th> : null}
              </tr>
            </thead>
            <tbody>
              {design.exercises.map((ex, i) => (
                <tr key={i} className="border-b border-emerald-50 last:border-0">
                  <td className="px-3 py-1.5">
                    {ex.exercise_id ? (
                      <Link
                        to={`/exercises/${ex.exercise_id}`}
                        className="text-emerald-700 underline decoration-emerald-300 underline-offset-2 hover:text-emerald-600"
                      >
                        {ex.name}
                      </Link>
                    ) : (
                      <span className="text-emerald-900">{ex.name}</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 text-muted-foreground">
                    {exerciseDetail(ex) || "-"}
                  </td>
                  {hasNotes ? (
                    <td className="px-3 py-1.5 text-[11px] text-muted-foreground/70">
                      {ex.notes || ""}
                    </td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {topRationale ? (
          <p className="mt-2 text-[11px] leading-relaxed text-emerald-800/80">
            <span className="font-medium">设计依据：</span>
            {topRationale}
          </p>
        ) : null}
      </div>

      {interactive && (
        <div className="flex items-center justify-between border-t border-emerald-100 px-4 py-2.5">
          <span className="text-[11px] text-muted-foreground">
            {submitted ? "已确认，等待设计下一日" : "确认后我将设计下一日；如需调整请直接说明"}
          </span>
          <Button
            size="sm"
            onClick={handleConfirm}
            disabled={!canSubmit}
            className={cn(
              "bg-emerald-600 text-white hover:bg-emerald-700",
              submitted && "opacity-60"
            )}
          >
            确认当日方案
          </Button>
        </div>
      )}
    </div>
  );
}
