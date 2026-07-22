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
    <div className="flex w-64 flex-col border-r bg-muted/30">
      {/* Logo */}
      <div className="flex items-center gap-2.5 border-b px-4 py-4">
        <div className="flex size-8 items-center justify-center rounded-lg bg-emerald-500/15">
          <DumbbellIcon className="size-4 text-emerald-400" />
        </div>
        <span className="text-base font-bold tracking-tight">FitCream</span>
      </div>

      {/* 导航 */}
      <div className="space-y-1 px-3 pt-3">
        <Link
          to="/dashboard"
          className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <LayoutDashboardIcon className="size-4" />
          工作台
        </Link>
        <div className="flex items-center gap-2.5 rounded-lg bg-muted px-3 py-2 text-sm font-medium">
          <MessageSquareIcon className="size-4 text-emerald-400" />
          AI 对话
        </div>
      </div>

      <div className="px-4 pt-4 pb-2">
        <Button onClick={onNewChat} className="w-full">
          <PlusIcon className="mr-2 size-4" />
          新对话
        </Button>
      </div>

      <p className="px-6 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/60">
        历史记录
      </p>

      <ScrollArea className="flex-1">
        <div className="space-y-1 px-2">
          {threads.map((thread) => (
            <div
              key={thread.id}
              className={cn(
                "group flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-muted",
                currentThreadId === thread.id && "bg-muted"
              )}
              onClick={() => onSelectThread(thread.id)}
            >
              <MessageSquareIcon className="size-4 shrink-0 text-muted-foreground" />
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

      <div className="border-t p-4">
        <p className="text-center text-xs text-muted-foreground">FitCream AI</p>
      </div>
    </div>
  );
}