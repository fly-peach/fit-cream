import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PlusIcon, TrashIcon, MessageSquareIcon, LayoutDashboardIcon, DumbbellIcon } from "lucide-react";
import type { Thread } from "@/types/chat";
import { cn } from "@/lib/utils";

interface SidebarProps {
  threads: Thread[];
  currentThreadId: string | null;
  onNewChat: () => void;
  onSelectThread: (id: string) => void;
  onDeleteThread: (id: string) => void;
}

export function Sidebar({
  threads,
  currentThreadId,
  onNewChat,
  onSelectThread,
  onDeleteThread,
}: SidebarProps) {
  return (
    <div className="flex w-64 flex-col border-r border-emerald-100 bg-gradient-to-b from-emerald-50/80 to-white/90 backdrop-blur">
      {/* Logo */}
      <div className="flex items-center gap-2.5 border-b border-emerald-100 px-4 py-4">
        <div className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 shadow-sm shadow-emerald-500/20">
          <DumbbellIcon className="size-4 text-white" />
        </div>
        <span className="text-base font-bold tracking-tight text-emerald-950">
          Fit<span className="text-emerald-600">Cream</span>
        </span>
      </div>

      {/* 导航 */}
      <div className="space-y-1 px-3 pt-3">
        <Link
          to="/dashboard"
          className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-emerald-700/70 transition-colors hover:bg-emerald-100/60 hover:text-emerald-800"
        >
          <LayoutDashboardIcon className="size-4" />
          工作台
        </Link>
        <div className="flex items-center gap-2.5 rounded-lg bg-emerald-100/80 px-3 py-2 text-sm font-semibold text-emerald-800">
          <MessageSquareIcon className="size-4 text-emerald-500" />
          AI 对话
        </div>
      </div>

      <div className="px-4 pt-4 pb-2">
        <Button
          onClick={onNewChat}
          className="w-full rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 text-white shadow-sm shadow-emerald-600/20 transition-all hover:from-emerald-500 hover:to-teal-500 active:scale-[0.98]"
        >
          <PlusIcon className="mr-2 size-4" />
          新对话
        </Button>
      </div>

      <p className="px-6 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-widest text-emerald-600/50">
        历史记录
      </p>

      <ScrollArea className="flex-1">
        <div className="space-y-1 px-2">
          {threads.map((thread) => (
            <div
              key={thread.id}
              className={cn(
                "group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm text-emerald-800/80 transition-colors hover:bg-emerald-100/60",
                currentThreadId === thread.id && "bg-emerald-100/80 font-medium text-emerald-900"
              )}
              onClick={() => onSelectThread(thread.id)}
            >
              <MessageSquareIcon className="size-4 shrink-0 text-emerald-400" />
              <span className="flex-1 truncate">{thread.title || "新对话"}</span>
              <Button
                variant="ghost"
                size="icon"
                className="size-6 opacity-0 group-hover:opacity-100"
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

      <div className="border-t border-emerald-100 p-4">
        <p className="text-center text-xs font-medium text-emerald-600/50">FitCream AI · 科学健身</p>
      </div>
    </div>
  );
}