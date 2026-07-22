import { useEffect, useRef } from "react";
import { useChatSSE } from "@/hooks/use-chat-sse";
import { useThreads } from "@/hooks/use-threads";
import { useChatStore } from "@/stores/chat-store";
import {
  Conversation,
  ConversationContent,
} from "@/components/ai-elements/conversation";
import {
  Message,
  MessageContent,
  MessageResponse,
} from "@/components/ai-elements/message";
import {
  Reasoning,
  ReasoningContent,
  ReasoningTrigger,
} from "@/components/ai-elements/reasoning";
import {
  Tool,
  ToolContent,
  ToolHeader,
  ToolInput,
  ToolOutput,
} from "@/components/ai-elements/tool";
import {
  PromptInput,
  PromptInputTextarea,
  PromptInputSubmit,
} from "@/components/ai-elements/prompt-input";
import { Sidebar } from "@/components/sidebar";
import { AppLayout } from "@/components/app-layout";
import { Button } from "@/components/ui/button";
import { SquareIcon, PlusIcon, BotMessageSquareIcon } from "lucide-react";
import type { ChatMessage } from "@/types/chat";

/** 工具名 -> 中文展示名映射，让工具调用块更易读 */
const toolNameMap: Record<string, string> = {
  query_stats_tool: "查询训练统计",
  query_checkins_tool: "查询打卡记录",
  query_plan_tool: "查询训练计划",
  query_body_tool: "查询身体数据",
  create_checkin_tool: "创建打卡记录",
  update_plan_tool: "更新训练计划",
  get_user_profile_tool: "读取用户档案",
  update_user_profile_tool: "更新用户档案",
};

/**
 * 清理模型回复中误以纯文本形式输出的工具调用标记。
 *
 * 部分模型会把工具调用以 `[调用 xxx(...)]` / `【调用 xxx】` 的文本写进 content，
 * 而真正的工具调用已由 Tool 组件单独渲染，这里需要把这类文本剔除，避免重复且难看。
 */
function cleanContent(text: string): string {
  if (!text) return "";
  return text
    .replace(/[\[【]\s*调用\s*[^\]】]*[\]】]/g, "")
    .replace(/\[?调用\s+\w+_tool\s*\([^)]*\)\]?/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function MessageItem({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <Message from="user">
        <MessageContent>{message.content}</MessageContent>
      </Message>
    );
  }

  // 过滤模型误输出的工具调用文本
  const cleaned = cleanContent(message.content);

  return (
    <Message from="assistant">
      <MessageContent>
        {message.thinking && (
          <Reasoning isStreaming={message.isStreaming && !message.content}>
            <ReasoningTrigger />
            <ReasoningContent>{message.thinking}</ReasoningContent>
          </Reasoning>
        )}

        {message.toolCalls?.map((tc) => (
          <Tool key={tc.id} defaultOpen={tc.status === "running"}>
            <ToolHeader
              title={toolNameMap[tc.name] ?? tc.name}
              type="tool-call"
              state={
                tc.status === "running"
                  ? "input-available"
                  : tc.status === "error"
                    ? "output-error"
                    : "output-available"
              }
            />
            <ToolContent>
              <ToolInput input={tc.input} />
              <ToolOutput output={tc.output} errorText={tc.error} />
            </ToolContent>
          </Tool>
        ))}

        {cleaned && <MessageResponse>{cleaned}</MessageResponse>}

        {message.isStreaming && !message.content && !message.thinking && (
          <span className="animate-pulse text-muted-foreground">▊</span>
        )}
      </MessageContent>
    </Message>
  );
}

export default function ChatPage() {
  const { currentThreadId, setThreadId } = useChatStore();
  const { messages, sendMessage, stop, clearMessages, isStreaming, setMessages } =
    useChatSSE(currentThreadId);
  const { threads, deleteThread } = useThreads();
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleNewChat = () => {
    setThreadId(null);
    clearMessages();
  };

  const handleSelectThread = async (id: string) => {
    setThreadId(id);
    // Load messages for thread
    const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";
    const token = localStorage.getItem("fitcream_token");
    try {
      const res = await fetch(`${API_URL}/chat/threads/${id}/messages`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const json = await res.json();
        // 后端 ResponseModel: { code, message, data: { messages, thread_id, total } }
        const data = json.data || {};
        setMessages(data.messages || []);
      }
    } catch {
      // ignore
    }
  };

  return (
    <AppLayout
      sidebarExtra={
        <Sidebar
          threads={threads}
          currentThreadId={currentThreadId}
          onNewChat={handleNewChat}
          onSelectThread={handleSelectThread}
          onDeleteThread={deleteThread}
        />
      }
    >
      <div className="flex h-full flex-col">
        {/* 页面顶部 header：AI 教练标题 + 新对话按钮（置于最上方） */}
        <header className="flex shrink-0 items-center justify-between border-b border-emerald-100 bg-white/70 px-4 py-2.5 backdrop-blur">
          <div className="flex items-center gap-2.5">
            <div className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 shadow-sm shadow-emerald-500/20">
              <BotMessageSquareIcon className="size-4 text-white" />
            </div>
            <div className="leading-tight">
              <h1 className="text-base font-bold text-emerald-950">AI 教练</h1>
              <p className="hidden text-xs text-emerald-600/60 sm:block">
                你的私人健身顾问
              </p>
            </div>
          </div>
          <Button
            onClick={handleNewChat}
            size="sm"
            variant="outline"
            className="gap-1.5 rounded-lg border-emerald-200 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800"
          >
            <PlusIcon className="size-4" />
            新对话
          </Button>
        </header>

        <Conversation className="flex-1">
          <ConversationContent>
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center gap-5">
                <div className="flex size-20 items-center justify-center rounded-3xl bg-gradient-to-br from-emerald-100 to-teal-100 shadow-inner">
                  <span className="text-4xl">🏋️</span>
                </div>
                <div className="text-center">
                  <p className="text-xl font-bold text-emerald-950">
                    Fit<span className="text-emerald-600">Cream</span> AI 健身教练
                  </p>
                  <p className="mt-2 text-sm text-emerald-700/60">
                    开始对话，获取个性化健身建议
                  </p>
                </div>
                <div className="mt-2 flex flex-wrap justify-center gap-2">
                  {["帮我制定减脂计划", "今天练什么好？", "饮食建议", "查看我的训练数据"].map(
                    (hint) => (
                      <button
                        key={hint}
                        type="button"
                        onClick={() => sendMessage(hint)}
                        className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 transition-all hover:border-emerald-300 hover:bg-emerald-100 active:scale-95"
                      >
                        {hint}
                      </button>
                    )
                  )}
                </div>
              </div>
            )}
            {messages.map((msg) => (
              <MessageItem key={msg.id} message={msg} />
            ))}
            <div ref={bottomRef} />
          </ConversationContent>
        </Conversation>

        <div className="border-t border-emerald-100 bg-white/70 p-4 backdrop-blur-sm">
          <PromptInput
            onSubmit={({ text }) => {
              if (text.trim()) sendMessage(text);
            }}
            className="mx-auto max-w-3xl"
          >
            <PromptInputTextarea placeholder="输入消息..." />
            <div className="flex items-center justify-end gap-2 pt-2">
              {isStreaming && (
                <Button variant="outline" size="sm" onClick={stop} type="button">
                  <SquareIcon className="mr-1 size-3" />
                  停止
                </Button>
              )}
              <PromptInputSubmit />
            </div>
          </PromptInput>
        </div>
      </div>
    </AppLayout>
  );
}
