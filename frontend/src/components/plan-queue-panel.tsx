/**
 * 计划设计待办队列面板（持久化顶部面板）
 *
 * 渲染 present_plan_queue_tool / update_plan_queue_item_tool 入参中的 PlanQueue：
 * - 每个 phase 一个可折叠 QueueSection（标题 + 完成数/总数）
 * - 每个 todo 一行：状态指示符 + 标题；completed 可展开看当日方案表格
 * - in_progress 行显示 spinner；skipped 显示删除线
 *
 * 面板数据由 chat.tsx 从全线程 messages.steps 中取最新队列快照传入，
 * 跨多轮用户消息始终反映最新进度。
 */

import { useState } from "react";
import {
  CheckIcon,
  ChevronDownIcon,
  DumbbellIcon,
  LoaderIcon,
  MinusIcon,
} from "lucide-react";
import {
  Queue,
  QueueSection,
  QueueSectionContent,
  QueueSectionLabel,
  QueueSectionTrigger,
  QueueList,
  QueueItem,
  QueueItemContent,
  QueueItemDescription,
} from "@/components/ai-elements/queue";
import { cn } from "@/lib/utils";
import type {
  DayExerciseDesign,
  PlanQueue,
  PlanQueueTodo,
} from "@/types/chat";

const WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

const TRAINING_TYPE_LABEL: Record<string, string> = {
  fat_loss: "减脂",
  muscle_gain: "增肌",
  recomp: "先减脂再增肌",
  cardio_only: "纯有氧",
  maintain: "维持",
};

function statusIndicator(status: PlanQueueTodo["status"]) {
  if (status === "completed") {
    return (
      <span className="mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
        <CheckIcon className="size-3" />
      </span>
    );
  }
  if (status === "in_progress") {
    return (
      <LoaderIcon className="mt-0.5 size-4 shrink-0 animate-spin text-emerald-600" />
    );
  }
  if (status === "skipped") {
    return (
      <span className="mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full border border-muted-foreground/30 text-muted-foreground/50">
        <MinusIcon className="size-3" />
      </span>
    );
  }
  return (
    <span className="mt-0.5 inline-block size-2.5 shrink-0 rounded-full border border-emerald-400" />
  );
}

function exerciseRow(ex: DayExerciseDesign, i: number) {
  const detail =
    ex.exercise_type === "cardio"
      ? [ex.duration_min ? `${ex.duration_min}分钟` : null, ex.distance_km ? `${ex.distance_km}km` : null]
          .filter(Boolean)
          .join(" ")
      : [
          ex.sets ? `${ex.sets}组` : null,
          ex.reps ? `${ex.reps}次` : null,
          ex.weight_kg ? `${ex.weight_kg}kg` : null,
        ]
          .filter(Boolean)
          .join(" · ");
  return (
    <tr key={i} className="border-b border-emerald-50 last:border-0">
      <td className="px-2 py-1 text-emerald-900">{ex.name}</td>
      <td className="px-2 py-1 text-muted-foreground">{detail || "-"}</td>
      {ex.notes ? (
        <td className="px-2 py-1 text-[11px] text-muted-foreground/70">{ex.notes}</td>
      ) : null}
    </tr>
  );
}

function DayDesignTable({ todo }: { todo: PlanQueueTodo }) {
  if (!todo.day_design) return null;
  const dd = todo.day_design;
  const hasNotes = dd.exercises.some((e) => e.notes);
  return (
    <div className="mt-1 overflow-x-auto rounded-lg border border-emerald-200">
      <div className="border-b border-emerald-100 bg-emerald-50/60 px-2.5 py-1.5 text-xs font-medium text-emerald-900">
        {WEEKDAYS[dd.day_of_week - 1]} · {dd.focus}
        <span className="ml-1.5 rounded bg-emerald-100 px-1.5 py-0.5 text-[10px] text-emerald-700">
          {dd.day_type}
        </span>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-emerald-100 bg-emerald-50/30 text-left text-emerald-800/70">
            <th className="px-2 py-1 font-medium">动作</th>
            <th className="px-2 py-1 font-medium">组次/重量</th>
            {hasNotes ? <th className="px-2 py-1 font-medium">说明</th> : null}
          </tr>
        </thead>
        <tbody>{dd.exercises.map((ex, i) => exerciseRow(ex, i))}</tbody>
      </table>
      {dd.rationale ? (
        <div className="border-t border-emerald-50 bg-emerald-50/20 px-2.5 py-1.5 text-[11px] text-emerald-800/80">
          设计依据：{dd.rationale}
        </div>
      ) : null}
    </div>
  );
}

function QueueTodoRow({ todo }: { todo: PlanQueueTodo }) {
  const completed = todo.status === "completed";
  const hasDesign = !!todo.day_design;
  const [open, setOpen] = useState(false);
  const clickable = completed && hasDesign;
  return (
    <QueueItem>
      <div
        className={cn("flex items-start gap-2", clickable && "cursor-pointer")}
        onClick={() => clickable && setOpen((v) => !v)}
      >
        {statusIndicator(todo.status)}
        <QueueItemContent completed={completed} className="text-foreground">
          {todo.title}
        </QueueItemContent>
        {clickable ? (
          <ChevronDownIcon
            className={cn(
              "size-3.5 shrink-0 text-muted-foreground transition-transform",
              open && "rotate-180"
            )}
          />
        ) : null}
      </div>
      {todo.description && !hasDesign ? (
        <QueueItemDescription completed={completed}>{todo.description}</QueueItemDescription>
      ) : null}
      {clickable && open ? <DayDesignTable todo={todo} /> : null}
    </QueueItem>
  );
}

export function PlanQueuePanel({ queue }: { queue: PlanQueue }) {
  const totalTodos = queue.phases.reduce((n, p) => n + p.todos.length, 0);
  const doneTodos = queue.phases.reduce(
    (n, p) => n + p.todos.filter((t) => t.status === "completed").length,
    0
  );
  return (
    <div className="mx-auto mb-3 w-full max-w-3xl">
      <Queue className="bg-emerald-50/30">
        <div className="flex items-center gap-2 px-1 pb-1 text-xs text-emerald-800/80">
          <DumbbellIcon className="size-3.5" />
          <span className="font-medium">
            计划设计进度 {doneTodos}/{totalTodos}
          </span>
          <span className="text-muted-foreground/70">
            · {TRAINING_TYPE_LABEL[queue.training_type] || queue.training_type}
            {" · "}
            每周{queue.weekly_frequency}天 · {queue.difficulty}
          </span>
        </div>
        {queue.phases.map((phase) => {
          const done = phase.todos.filter((t) => t.status === "completed").length;
          return (
            <QueueSection key={phase.phase_id} defaultOpen>
              <QueueSectionTrigger>
                <QueueSectionLabel
                  count={done}
                  label={`/ ${phase.todos.length} · ${phase.phase_title}`}
                  icon={<DumbbellIcon className="size-3.5 text-emerald-600" />}
                />
              </QueueSectionTrigger>
              <QueueSectionContent>
                <QueueList>
                  {phase.todos.map((todo) => (
                    <QueueTodoRow key={todo.id} todo={todo} />
                  ))}
                </QueueList>
              </QueueSectionContent>
            </QueueSection>
          );
        })}
      </Queue>
    </div>
  );
}
