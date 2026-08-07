/**
 * 计划设计待办队列面板（持久化顶部面板）
 *
 * 只渲染待办：队列标题 + 各 todo 的标题与状态指示（○待办/▸进行中/✓完成/·跳过）。
 * 不含表单、当日方案等内容--那些都在对话消息流内渲染（FormCard / DayDesignCard）。
 *
 * 面板数据由 chat.tsx 从全线程 messages.steps 取最新队列快照传入，
 * 跨多轮用户消息始终反映最新进度。
 */

import {
  CheckIcon,
  DumbbellIcon,
  LoaderIcon,
  MinusIcon,
} from "lucide-react";
import { Queue, QueueList, QueueItem } from "@/components/ai-elements/queue";
import { cn } from "@/lib/utils";
import type { PlanQueue, PlanQueueTodo } from "@/types/chat";

function StatusIndicator({ status }: { status: PlanQueueTodo["status"] }) {
  if (status === "completed") {
    return (
      <span className="mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
        <CheckIcon className="size-3" />
      </span>
    );
  }
  if (status === "in_progress") {
    return <LoaderIcon className="mt-0.5 size-4 shrink-0 animate-spin text-emerald-600" />;
  }
  if (status === "skipped") {
    return (
      <span className="mt-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-full border border-muted-foreground/30 text-muted-foreground/50">
        <MinusIcon className="size-3" />
      </span>
    );
  }
  return <span className="mt-0.5 inline-block size-2.5 shrink-0 rounded-full border border-emerald-400" />;
}

export function PlanQueuePanel({ queue }: { queue: PlanQueue }) {
  const todos = queue.todos || [];
  const done = todos.filter((t) => t.status === "completed").length;
  return (
    <div className="mx-auto mb-3 w-full max-w-3xl">
      <Queue className="bg-emerald-50/30">
        <div className="flex items-center gap-2 px-1 pb-1 text-xs text-emerald-800/80">
          <DumbbellIcon className="size-3.5" />
          <span className="font-medium">{queue.title}</span>
          <span className="text-muted-foreground/70">
            {done}/{todos.length}
          </span>
        </div>
        <QueueList>
          {todos.map((todo) => (
            <QueueItem key={todo.id} className="flex-row items-center gap-2 py-1">
              <StatusIndicator status={todo.status} />
              <span
                className={cn(
                  "line-clamp-1 text-sm",
                  todo.status === "completed" && "text-muted-foreground/50 line-through",
                  todo.status === "in_progress" && "font-medium text-emerald-900",
                  todo.status === "pending" && "text-foreground",
                  todo.status === "skipped" && "text-muted-foreground/40 line-through"
                )}
              >
                {todo.title}
              </span>
            </QueueItem>
          ))}
        </QueueList>
      </Queue>
    </div>
  );
}
