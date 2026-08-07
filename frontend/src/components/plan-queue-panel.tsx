/**
 * 计划设计待办队列面板
 *
 * 参考 ai-sdk elements queue 组件结构：
 * - Queue + QueueSection 包裹，max-h 可滚动
 * - TodoItem：QueueItemIndicator（完成打点）+ QueueItemContent（标题，完成划线）
 *   + QueueItemActions 悬停显示移除按钮 + QueueItemDescription（可选说明）
 * - in_progress 用 spinner 指示；skipped 视为完成态降透明度
 *
 * 移除按钮发结构化消息「[移除待办: <id>]」回对话，由 agent 更新队列快照。
 * 面板数据由 chat.tsx 从全线程 messages.steps 取最新队列快照传入。
 */

import { memo, useCallback } from "react";
import { LoaderIcon, Trash2 } from "lucide-react";
import {
  Queue,
  QueueItem,
  QueueItemAction,
  QueueItemActions,
  QueueItemContent,
  QueueItemDescription,
  QueueItemIndicator,
  QueueSection,
  QueueSectionContent,
} from "@/components/ai-elements/queue";
import { cn } from "@/lib/utils";
import type { PlanQueue, PlanQueueTodo } from "@/types/chat";

interface TodoItemProps {
  todo: PlanQueueTodo;
  onRemove: (id: string) => void;
}

const TodoItem = memo(({ todo, onRemove }: TodoItemProps) => {
  const isCompleted = todo.status === "completed";
  const isSkipped = todo.status === "skipped";
  const isInProgress = todo.status === "in_progress";
  const done = isCompleted || isSkipped;
  const handleRemove = useCallback(() => onRemove(todo.id), [onRemove, todo.id]);

  return (
    <QueueItem key={todo.id}>
      <div className="flex items-center gap-2">
        {isInProgress ? (
          <LoaderIcon className="size-3 shrink-0 animate-spin text-emerald-600" />
        ) : (
          <QueueItemIndicator completed={done} />
        )}
        <QueueItemContent
          completed={done}
          className={cn(isSkipped && "opacity-40")}
        >
          {todo.title}
        </QueueItemContent>
        <QueueItemActions>
          <QueueItemAction aria-label="移除待办" onClick={handleRemove}>
            <Trash2 size={12} />
          </QueueItemAction>
        </QueueItemActions>
      </div>
      {todo.description && (
        <QueueItemDescription completed={done}>{todo.description}</QueueItemDescription>
      )}
    </QueueItem>
  );
});

TodoItem.displayName = "TodoItem";

export function PlanQueuePanel({
  queue,
  onAction,
}: {
  queue: PlanQueue;
  onAction?: (text: string) => void;
}) {
  const todos = queue.todos || [];
  const done = todos.filter((t) => t.status === "completed").length;
  const handleRemove = useCallback(
    (id: string) => onAction?.(`[移除待办: ${id}]`),
    [onAction]
  );

  return (
    <div className="mx-auto w-full max-w-3xl">
      <Queue className="mx-auto max-h-[150px] w-full overflow-y-auto rounded-b-none border-input border-b-0 px-3 pt-2 pb-1">
        <div className="flex items-center gap-2 px-1 pb-1 text-xs text-emerald-800/80">
          <span className="font-medium">{queue.title}</span>
          <span className="text-muted-foreground/70">
            {done}/{todos.length}
          </span>
        </div>
        {todos.length > 0 && (
          <QueueSection>
            <QueueSectionContent>
              <div>
                {todos.map((todo) => (
                  <TodoItem key={todo.id} todo={todo} onRemove={handleRemove} />
                ))}
              </div>
            </QueueSectionContent>
          </QueueSection>
        )}
      </Queue>
    </div>
  );
}
