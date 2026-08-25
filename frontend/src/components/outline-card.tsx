/**
 * 训练大纲卡片
 *
 * 把 present_outline_tool 步骤渲染为对话内的「查看训练大纲」链接（chip），
 * 点击弹窗展示完整大纲（分化策略 + 每日安排表格）--不占 SSE 正文流。
 *
 * - 确认按钮：发结构化消息「[确认大纲]」回到对话（复用 sendMessage）
 * - 交互态同 FormCard / DayDesignCard：仅最新助手消息且非流式时可点；提交后置灰「已确认」
 */

import { useState } from "react";
import { CheckCircle2Icon, ClipboardListIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { AgentStep, PlanOutline } from "@/types/chat";

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

const DAY_TYPE_LABELS: Record<string, string> = {
  strength: "力量",
  cardio: "有氧",
  mixed: "混合",
  rest: "休息",
};

interface OutlineCardProps {
  step: AgentStep;
  interactive: boolean;
  onSubmit: (text: string) => void;
}

export function OutlineCard({ step, interactive, onSubmit }: OutlineCardProps) {
  const input = (step.input || {}) as Partial<PlanOutline>;
  const days = Array.isArray(input.days)
    ? [...input.days].sort((a, b) => a.day_of_week - b.day_of_week)
    : [];
  const [submitted, setSubmitted] = useState(false);
  const [open, setOpen] = useState(false);

  if (!days.length) return null;

  const canSubmit = interactive && !submitted;

  const handleConfirm = () => {
    if (!canSubmit) return;
    onSubmit("[确认大纲]");
    setSubmitted(true);
    setOpen(false);
  };

  return (
    <div className="my-1 flex items-center gap-2">
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50/60 px-3 py-1 text-xs font-medium text-emerald-700 transition-colors hover:bg-emerald-100"
      >
        <ClipboardListIcon className="size-3.5" />
        查看训练大纲
      </button>
      {submitted && (
        <span className="inline-flex items-center gap-1 text-xs text-emerald-600">
          <CheckCircle2Icon className="size-3" />
          已确认
        </span>
      )}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{input.title || "训练大纲"}</DialogTitle>
            {input.strategy ? (
              <DialogDescription className="leading-relaxed">
                {input.strategy}
              </DialogDescription>
            ) : null}
          </DialogHeader>
          <div className="overflow-x-auto rounded-lg border border-emerald-200">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-emerald-100 bg-emerald-50/30 text-left text-emerald-800/70">
                  <th className="px-3 py-1.5 font-medium">星期</th>
                  <th className="px-3 py-1.5 font-medium">训练重点</th>
                  <th className="px-3 py-1.5 font-medium">类型</th>
                  {days.some((d) => d.note) ? (
                    <th className="px-3 py-1.5 font-medium">备注</th>
                  ) : null}
                </tr>
              </thead>
              <tbody>
                {days.map((d, i) => (
                  <tr key={i} className="border-b border-emerald-50 last:border-0">
                    <td className="px-3 py-1.5 text-emerald-900">
                      {WEEKDAYS[d.day_of_week - 1]}
                    </td>
                    <td className="px-3 py-1.5 text-emerald-900">{d.focus}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">
                      {DAY_TYPE_LABELS[d.day_type] || d.day_type}
                    </td>
                    {days.some((x) => x.note) ? (
                      <td className="px-3 py-1.5 text-[11px] text-muted-foreground/70">
                        {d.note || ""}
                      </td>
                    ) : null}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {interactive && (
            <DialogFooter>
              <span className="mr-auto max-w-[16rem] text-[11px] leading-snug text-muted-foreground">
                {submitted
                  ? "已确认，开始逐日设计"
                  : "确认后进入逐日设计；如需调整分化/频率请直接说明"}
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
                确认大纲
              </Button>
            </DialogFooter>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
