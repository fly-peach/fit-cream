/**
 * 闯关路线图视图（独立于聊天卡片的页面级组件）
 *
 * 渲染完整路线图：关卡纵向时间线（序号/标题/状态徽标/预期周数/出口条件/训练重点），
 * 当前关（status=active）高亮。
 *
 * 数据源：GET /api/goal-roadmap 的 data.roadmap（含 milestones）。
 * 复用：训练计划页（完整）、Dashboard（compact 当前关节点）。
 */

import { Link } from "react-router-dom";
import { CheckCircle2Icon, FlagIcon, LockIcon, MapIcon, TargetIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface RoadmapCriterionView {
  metric: string;
  op: ">=" | "<=";
  value: number;
  unit?: string;
}

export interface RoadmapMilestoneView {
  id: string;
  stage_index: number;
  title: string;
  description?: string | null;
  exit_criteria: RoadmapCriterionView[];
  expected_weeks?: number | null;
  status: "locked" | "active" | "achieved" | "skipped";
  achieved_at?: string | null;
  training_focus?: string | null;
}

export interface RoadmapViewData {
  id: string;
  archetype_key?: string | null;
  title: string;
  description?: string | null;
  horizon_months?: number | null;
  status?: string | null;
  milestones: RoadmapMilestoneView[];
}

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

export function criterionText(c: RoadmapCriterionView): string {
  const opText = c.op === ">=" ? "≥" : "≤";
  const unit = c.unit || METRIC_UNITS[c.metric] || "";
  const value = Number.isInteger(c.value) ? c.value : c.value.toFixed(1);
  return `${metricLabel(c.metric)} ${opText} ${value}${unit}`;
}

const STATUS_META: Record<
  RoadmapMilestoneView["status"],
  { label: string; cls: string; dot: string }
> = {
  achieved: {
    label: "已通关",
    cls: "bg-emerald-100 text-emerald-700",
    dot: "bg-emerald-500",
  },
  active: {
    label: "进行中",
    cls: "bg-sky-100 text-sky-700",
    dot: "bg-sky-500",
  },
  locked: {
    label: "未解锁",
    cls: "bg-muted text-muted-foreground",
    dot: "bg-muted-foreground/40",
  },
  skipped: {
    label: "已跳过",
    cls: "bg-gray-100 text-gray-500",
    dot: "bg-gray-400",
  },
};

function MilestoneNode({ m, isLast }: { m: RoadmapMilestoneView; isLast: boolean }) {
  const meta = STATUS_META[m.status] ?? STATUS_META.locked;
  return (
    <li className="relative pl-8">
      <span
        className={cn(
          "absolute left-0 top-0 flex size-7 items-center justify-center rounded-full text-xs font-bold ring-4",
          m.status === "achieved"
            ? "bg-emerald-500 text-white ring-emerald-100"
            : m.status === "active"
              ? "bg-sky-600 text-white ring-sky-100"
              : "bg-muted text-muted-foreground ring-gray-100",
        )}
      >
        {m.status === "achieved" ? (
          <CheckCircle2Icon className="size-4" />
        ) : m.status === "locked" ? (
          <LockIcon className="size-3.5" />
        ) : (
          m.stage_index
        )}
      </span>
      <div
        className={cn(
          "rounded-lg border px-3 py-2",
          m.status === "active"
            ? "border-sky-200 bg-sky-50/50 shadow-sm"
            : m.status === "achieved"
              ? "border-emerald-100 bg-emerald-50/30"
              : "border-gray-100 bg-gray-50/40",
        )}
      >
        <div className="flex items-center gap-2">
          <span
            className={cn(
              "text-sm font-medium",
              m.status === "active"
                ? "text-sky-950"
                : m.status === "achieved"
                  ? "text-emerald-800"
                  : "text-gray-500",
            )}
          >
            {m.status === "locked" ? `${m.stage_index} · ${m.title}` : m.title}
          </span>
          {m.expected_weeks ? (
            <span className="rounded bg-white/70 px-1.5 py-0.5 text-[10px] text-muted-foreground">
              约 {m.expected_weeks} 周
            </span>
          ) : null}
          <span
            className={cn(
              "ml-auto inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
              meta.cls,
            )}
          >
            <span className={cn("size-1.5 rounded-full", meta.dot)} />
            {meta.label}
          </span>
        </div>
        {m.description ? (
          <p className="mt-1 text-xs text-muted-foreground/80">{m.description}</p>
        ) : null}
        <ul className="mt-1.5 space-y-0.5">
          {m.exit_criteria.map((c, j) => (
            <li key={j} className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <TargetIcon className="size-3 shrink-0 text-sky-500" />
              {criterionText(c)}
            </li>
          ))}
        </ul>
        {m.training_focus ? (
          <div className="mt-1 text-[11px] text-muted-foreground/70">
            训练重点：{m.training_focus}
          </div>
        ) : null}
      </div>
      {!isLast ? (
        <span className="absolute left-[13px] top-8 bottom-[-16px] w-px bg-gray-200" aria-hidden />
      ) : null}
    </li>
  );
}

interface RoadmapViewProps {
  roadmap: RoadmapViewData | null;
}

export function RoadmapView({ roadmap }: RoadmapViewProps) {
  if (!roadmap || roadmap.milestones.length === 0) {
    return (
      <div className="flex flex-col items-center gap-2 rounded-xl border border-dashed border-emerald-200 bg-emerald-50/20 px-4 py-6 text-center">
        <MapIcon className="size-6 text-emerald-300" />
        <p className="text-sm text-emerald-700/70">还没有闯关路线图</p>
        <p className="text-xs text-emerald-500/60">
          在 AI 教练聊天页点「设计计划」，先确定目标身材原型即可生成路线图
        </p>
        <Link
          to="/chat"
          className="mt-1 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
        >
          去 AI 教练
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2.5">
        <MapIcon className="mt-0.5 size-4 shrink-0 text-sky-600" />
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-sm font-semibold text-sky-950">
            {roadmap.title}
            {roadmap.horizon_months ? (
              <span className="rounded bg-sky-100 px-1.5 py-0.5 text-[10px] font-normal text-sky-700">
                约 {roadmap.horizon_months} 个月
              </span>
            ) : null}
          </div>
          {roadmap.description ? (
            <p className="mt-0.5 text-xs text-muted-foreground/80">{roadmap.description}</p>
          ) : null}
        </div>
      </div>

      <ol className="relative space-y-4">
        {roadmap.milestones.map((m, i) => (
          <MilestoneNode key={m.id} m={m} isLast={i === roadmap.milestones.length - 1} />
        ))}
      </ol>

      <p className="flex items-center gap-1 text-[11px] text-muted-foreground">
        <FlagIcon className="size-3" />
        关卡是检查点而非日期承诺：周数为排期参考，出关以复测达标为准。
      </p>
    </div>
  );
}
