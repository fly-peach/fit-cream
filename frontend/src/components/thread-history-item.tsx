import { useCallback, useRef } from "react";
import { PencilIcon, Trash2Icon, ZapIcon } from "lucide-react";
import type { Thread } from "@/types/chat";
import { formatThreadTime, threadDisplayTitle } from "@/lib/thread";

/** 会话历史条目：展示标题 / 创建时间 / Token，支持内联重命名与删除 */
interface ThreadHistoryItemProps {
  thread: Thread;
  isActive: boolean;
  isEditing: boolean;
  onSelect: () => void;
  onDelete: () => void;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onRename: (title: string) => Promise<boolean>;
}

export function ThreadHistoryItem({
  thread,
  isActive,
  isEditing,
  onSelect,
  onDelete,
  onStartEdit,
  onCancelEdit,
  onRename,
}: ThreadHistoryItemProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelledRef = useRef(false);

  const commit = useCallback(async () => {
    const value = (inputRef.current?.value ?? "").trim();
    const current = threadDisplayTitle(thread);
    onCancelEdit();
    if (!value || value === current) return;
    await onRename(value);
  }, [thread, onCancelEdit, onRename]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      void commit();
    } else if (e.key === "Escape") {
      cancelledRef.current = true;
      onCancelEdit();
    }
  };

  const handleBlur = () => {
    if (cancelledRef.current) {
      cancelledRef.current = false;
      return;
    }
    void commit();
  };

  return (
    <div
      className={`group flex cursor-pointer flex-col gap-1 rounded-lg px-3 py-2.5 transition-colors ${
        isActive ? "bg-emerald-100 text-emerald-900" : "text-emerald-800 hover:bg-emerald-50"
      }`}
      onClick={onSelect}
    >
      <div className="flex items-center gap-2">
        {isEditing ? (
          <input
            ref={inputRef}
            key={`edit-${thread.id}`}
            defaultValue={threadDisplayTitle(thread)}
            autoFocus
            onFocus={(e) => e.target.select()}
            onKeyDown={handleKeyDown}
            onBlur={handleBlur}
            onClick={(e) => e.stopPropagation()}
            maxLength={200}
            className="min-w-0 flex-1 rounded border border-emerald-300 bg-white px-1.5 py-0.5 text-sm text-emerald-900 outline-none focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500"
            placeholder="输入会话名称"
          />
        ) : (
          <span className="line-clamp-1 flex-1 text-sm font-medium">
            {threadDisplayTitle(thread)}
          </span>
        )}
        {!isEditing && (
          <div className="flex shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              type="button"
              title="重命名"
              onClick={(e) => {
                e.stopPropagation();
                onStartEdit();
              }}
              className="rounded p-1 text-emerald-400 hover:bg-emerald-200/60 hover:text-emerald-700"
            >
              <PencilIcon className="size-3" />
            </button>
            <button
              type="button"
              title="删除"
              onClick={(e) => {
                e.stopPropagation();
                onDelete();
              }}
              className="rounded p-1 text-emerald-400 hover:bg-red-100 hover:text-red-500"
            >
              <Trash2Icon className="size-3.5" />
            </button>
          </div>
        )}
      </div>
      <div className="flex items-center gap-3 text-[11px] text-emerald-500/70">
        <span className="flex items-center gap-0.5">
          <ZapIcon className="size-3" />
          {thread.totalTokens > 0 ? `${(thread.totalTokens / 1000).toFixed(1)}k tokens` : "0 tokens"}
        </span>
        <span>{thread.messageCount} 条消息</span>
        <span className="ml-auto tabular-nums">{formatThreadTime(thread.createdAt)}</span>
      </div>
    </div>
  );
}
