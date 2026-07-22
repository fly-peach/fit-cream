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
import { Button } from "@/components/ui/button";
import { SquareIcon } from "lucide-react";
import type { ChatMessage } from "@/types/chat";

function MessageItem({ message }: { message: ChatMessage }) {
  if (message.role === "user") {
    return (
      <Message from="user">
        <MessageContent>{message.content}</MessageContent>
      </Message>
    );
  }

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
              title={tc.name}
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

        {message.content && <MessageResponse>{message.content}</MessageResponse>}

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
    <div className="flex h-screen bg-gradient-to-br from-emerald-50/80 via-white to-teal-50/60">
      <Sidebar
        threads={threads}
        currentThreadId={currentThreadId}
        onNewChat={handleNewChat}
        onSelectThread={handleSelectThread}
        onDeleteThread={deleteThread}
      />

      <div className="flex flex-1 flex-col">
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
                  {["帮我制定减脂计划", "今天练什么好？", "饮食建议"].map((hint) => (
                    <span
                      key={hint}
                      className="rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700"
                    >
                      {hint}
                    </span>
                  ))}
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
    </div>
  );
}