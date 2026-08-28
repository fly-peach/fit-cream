/**
 * 闯关路线图卡片
 *
 * 把 present_roadmap_tool 步骤渲染为纵向关卡时间线提案：
 * - 每个关卡：序号 / 标题 / 预期周数 / 出口条件列表 / 训练重点
 * - 底部确认按钮：发结构化消息「[确认路线图]」回到对话（复用 sendMessage）
 *
 * 交互态同 DayDesignCard：仅最新助手消息且非流式时可点；提交后置灰「已确认」。
 */

import { useState } from "react";
import { CheckCircle2Icon, MapIcon, TargetIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { AgentStep, RoadmapStage } from "@/types/chat";

const METRIC_LABELS: Record<string, string> = {
  body_fat_pct: "体脂率",
  bench_kg: "卧推",
  squat_kg: "深蹲",
  deadlift_kg: "硬拉",
  ohp_kg: "站姿推举",
  pull_ups: "引体向上",
  waist_cm: "腰围",
  bodyweight_kg: "体重",
  bench_ratio: "卧推(×体重)",
  squat_ratio: "深蹲(×体重)",
  deadlift_ratio: "硬拉(×体重)",
  ohp_ratio: "推举(×体重)",
};

const METRIC_UNITS: Record<string, string> = {
  body_fat_pct: "%",
  bench_kg: "kg",
  squat_kg: "kg",
  deadlift_kg: "kg",
  ohp_kg: "kg",
  pull_ups: "次",
  waist_cm: "cm",
  bodyweight_kg: "kg",
};

function metricLabel(metric: string): string {
  return METRIC_LABELS[metric] || metric;
}

function criterionText(c: {
  metric: string;
  op: ">=" | "<=";
  value: number;
  unit?: string;
}): string {
  const opText = c.op === ">=" ? "≥" : "≤";
  const unit = c.unit || METRIC_UNITS[c.metric] || "";
  const value = Number.isInteger(c.value) ? c.value : c.value.toFixed(1);
  return `${metricLabel(c.metric)} ${opText} ${value}${unit}`;
}

interface RoadmapCardProps {
  step: AgentStep;
  interactive: boolean;
  onSubmit: (text: string) => void;
}

export function RoadmapCard({ step, interactive, onSubmit }: RoadmapCardProps) {
  const input = (step.input || {}) as {
    title?: string;
    description?: string;
    stages?: RoadmapStage[];
  };
  const stages = input.stages || [];
  const [submitted, setSubmitted] = useState(false);

  if (!input.title && stages.length === 0) return null;

  const canSubmit = interactive && !submitted;

  const handleConfirm = () => {
    if (!canSubmit) return;
    onSubmit("[确认路线图]");
    setSubmitted(true);
  };

  return (
    <div className="my-2 overflow-hidden rounded-xl border border-sky-200 bg-white shadow-sm">
      <div className="flex items-start gap-2.5 border-b border-sky-100 bg-sky-50/40 px-4 py-3">
        <MapIcon className="mt-0.5 size-4 shrink-0 text-sky-600" />
        <div className="min-w-0">
          <div className="text-sm font-semibold text-sky-950">{input.title || "闯关路线图"}</div>
          {input.description ? (
            <div className="mt-0.5 text-xs text-sky-700/70">{input.description}</div>
          ) : null}
        </div>
        {submitted && (
          <span className="ml-auto inline-flex shrink-0 items-center gap-1 rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-700">
            <CheckCircle2Icon className="size-3" />
            已确认
          </span>
        )}
      </div>

      <div className="px-4 py-3">
        <ol className="relative space-y-4 before:absolute before:left-[13px] before:top-2 before:bottom-2 before:w-px before:bg-sky-200">
          {stages.map((st, i) => (
            <li key={i} className="relative pl-8">
              <span className="absolute left-0 top-0 flex size-7 items-center justify-center rounded-full bg-sky-600 text-xs font-bold text-white ring-4 ring-sky-100">
                {st.stage_index}
              </span>
              <div className="rounded-lg border border-sky-100 bg-sky-50/30 px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-sky-950">{st.title}</span>
                  {st.expected_weeks ? (
                    <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] text-sky-700">
                      约 {st.expected_weeks} 周
                    </span>
                  ) : null}
                </div>
                <ul className="mt-1.5 space-y-0.5">
                  {st.exit_criteria.map((c, j) => (
                    <li key={j} className="flex items-center gap-1.5 text-xs text-sky-800/80">
                      <TargetIcon className="size-3 shrink-0 text-sky-500" />
                      {criterionText(c)}
                    </li>
                  ))}
                </ul>
                {st.training_focus ? (
                  <div className="mt-1 text-[11px] text-sky-700/70">
                    训练重点：{st.training_focus}
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ol>
        <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground">
          关卡是检查点而非日期承诺：周数为排期参考，出关以复测达标为准。
        </p>
      </div>

      {interactive && (
        <div className="flex items-center justify-between border-t border-sky-100 px-4 py-2.5">
          <span className="text-[11px] text-muted-foreground">
            {submitted ? "已确认，正在创建路线图" : "确认后我将创建路线图并进入计划设计；如需调整请直接说明"}
          </span>
          <Button
            size="sm"
            onClick={handleConfirm}
            disabled={!canSubmit}
            className={cn(
              "bg-sky-600 text-white hover:bg-sky-700",
              submitted && "opacity-60"
            )}
          >
            确认路线图
          </Button>
        </div>
      )}
    </div>
  );
}
