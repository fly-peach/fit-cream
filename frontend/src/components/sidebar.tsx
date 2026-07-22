import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PlusIcon, TrashIcon, MessageSquareIcon, SparklesIcon } from "lucide-react";
import type { Thread } from "@/types/chat";
import { cn } from "@/lib/utils";

interface SidebarProps {
  threads: Thread[];
  currentThreadId: string | null;
  onNewChat: () => void;
  onSelectThread: (id: string) => void;
  onDeleteThread: (id: string) => void;
}

/**
 * 对话侧边栏附加面板
 *
 * 仅渲染「新对话」按钮与历史会话列表，作为 AppLayout 的 sidebarExtra 插槽。
 * 全局导航（工作台 / AI 教练 / 计划 …）由 AppLayout 统一提供。
 */
export function Sidebar({
  threads,
  currentThreadId,
  onNewChat,
  onSelectThread,
  onDeleteThread,
}: SidebarProps) {
  return (
    <div className="flex h-full flex-col">
      <div className="px-3 pt-4 pb-2">
        <Button
          onClick={onNewChat}
          className="group w-full rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-sm shadow-emerald-600/20 transition-all hover:from-emerald-500 hover:to-teal-500 hover:shadow-md hover:shadow-emerald-600/30 active:scale-[0.98]"
        >
          <PlusIcon className="mr-2 size-4 transition-transform group-hover:rotate-90" />
          新对话
        </Button>
      </div>

      <div className="flex items-center justify-between px-5 pb-1 pt-3">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-emerald-600/50">
          历史记录
        </p>
        <span className="rounded-full bg-emerald-100/70 px-1.5 text-[10px] font-medium tabular-nums text-emerald-600">
          {threads.length}
        </span>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-1 px-2 pb-2">
          {threads.length === 0 && (
            <div className="flex flex-col items-center gap-2 px-4 py-8 text-center">
              <div className="flex size-9 items-center justify-center rounded-xl bg-emerald-100/70">
                <SparklesIcon className="size-4 text-emerald-500" />
              </div>
              <p className="text-xs text-emerald-600/60">还没有对话，点击上方开始</p>
            </div>
          )}
          {threads.map((thread) => (
            <div
              key={thread.id}
              className={cn(
                "group relative flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all duration-150",
                currentThreadId === thread.id
                  ? "bg-emerald-100/80 font-medium text-emerald-900 shadow-sm"
                  : "text-emerald-800/80 hover:bg-emerald-100/60 hover:text-emerald-900"
              )}
              onClick={() => onSelectThread(thread.id)}
            >
              {currentThreadId === thread.id && (
                <span className="absolute left-0 top-1/2 h-5 w-1 -translate-y-1/2 rounded-r-full bg-emerald-500" />
              )}
              <MessageSquareIcon
                className={cn(
                  "size-4 shrink-0 transition-colors",
                  currentThreadId === thread.id
                    ? "text-emerald-500"
                    : "text-emerald-400 group-hover:text-emerald-500"
                )}
              />
              <span className="flex-1 truncate">{thread.title || "新对话"}</span>
              <Button
                variant="ghost"
                size="icon"
                className="size-6 shrink-0 opacity-0 transition-opacity hover:bg-red-100 hover:text-red-600 group-hover:opacity-100"
                onClick={(e) => {
                  e.stopPropagation();
                  onDeleteThread(thread.id);
                }}
              >
                <TrashIcon className="size-3" />
              </Button>
            </div>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}