import { memo, useCallback, useEffect, useRef, type ChangeEvent } from "react";
import { Link } from "react-router-dom";
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
  Attachments,
  Attachment,
  AttachmentPreview,
  AttachmentRemove,
} from "@/components/ai-elements/attachments";
import {
  PromptInput,
  PromptInputActionAddAttachments,
  PromptInputActionMenu,
  PromptInputActionMenuContent,
  PromptInputActionMenuTrigger,
  PromptInputBody,
  PromptInputButton,
  PromptInputFooter,
  PromptInputProvider,
  PromptInputTextarea,
  PromptInputSubmit,
  PromptInputTools,
  usePromptInputAttachments,
  type PromptInputMessage,
} from "@/components/ai-elements/prompt-input";
import {
  Context,
  ContextContent,
  ContextContentBody,
  ContextContentFooter,
  ContextContentHeader,
  ContextInputUsage,
  ContextOutputUsage,
  ContextTrigger,
} from "@/components/ai-elements/context";
import { AppLayout } from "@/components/app-layout";
import { Button, buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  PlusIcon,
  BotMessageSquareIcon,
  HistoryIcon,
  XIcon,
  Trash2Icon,
  ZapIcon,
  CameraIcon,
  BookOpenIcon,
} from "lucide-react";
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
    const hasImages = !!message.images && message.images.length > 0;
    const hasText = !!message.content && message.content !== "[图片消息]";
    return (
      <Message from="user">
        <MessageContent>
          {hasImages && (
            <div className="mb-2 flex flex-wrap justify-end gap-2">
              {message.images!.map((url, i) => (
                <img
                  key={i}
                  src={url}
                  alt={`图片 ${i + 1}`}
                  loading="lazy"
                  className="max-h-52 rounded-lg border border-emerald-100 object-cover shadow-sm"
                />
              ))}
            </div>
          )}
          {hasText && <span>{message.content}</span>}
        </MessageContent>
      </Message>
    );
  }

  // 过滤模型误输出的工具调用文本
  const cleaned = cleanContent(message.content);
  const hasThinking = !!message.thinking;
  const hasToolCalls = !!message.toolCalls?.length;
  // 只要有 thinking 或 toolCalls，就展示 Reasoning 折叠块（chain-of-thought 模式）
  const showReasoning = hasThinking || hasToolCalls;
  const isThinking = message.isStreaming && !message.content;

  return (
    <Message from="assistant">
      <MessageContent>
        {showReasoning && (
          <Reasoning isStreaming={isThinking}>
            <ReasoningTrigger />
            <ReasoningContent>
              {/* 思考文本 */}
              {message.thinking && (
                <div className="whitespace-pre-wrap">{message.thinking}</div>
              )}
              {/* 工具调用嵌套在思考过程内部（chain-of-thought 模式） */}
              {hasToolCalls && (
                <div className={message.thinking ? "mt-3 space-y-2 border-t border-border/50 pt-3" : "space-y-2"}>
                  {message.toolCalls!.map((tc) => (
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
                </div>
              )}
            </ReasoningContent>
          </Reasoning>
        )}

        {cleaned && <MessageResponse>{cleaned}</MessageResponse>}

        {message.isStreaming && !message.content && !showReasoning && (
          <span className="animate-pulse text-muted-foreground">▊</span>
        )}
      </MessageContent>
    </Message>
  );
}

/** 上下文窗口最大 Token 数（与后端 Summarization 触发阈值一致） */
const MAX_CONTEXT_TOKENS = 100_000;

/** 单张图片大小上限：与后端 /api/chat/upload-image 的 MAX_IMAGE_SIZE 一致（10MB） */
const MAX_IMAGE_SIZE = 10 * 1024 * 1024;
/** 最多同时上传图片数量：与后端 ChatRequest.images 限制一致 */
const MAX_IMAGE_FILES = 10;

/** 单个附件项（memo 优化重渲染，参考 ai-elements prompt-input 示例） */
interface AttachmentItemProps {
  attachment: {
    id: string;
    type: "file";
    filename?: string;
    mediaType?: string;
    url: string;
  };
  onRemove: (id: string) => void;
}

const AttachmentItem = memo(({ attachment, onRemove }: AttachmentItemProps) => {
  const handleRemove = useCallback(
    () => onRemove(attachment.id),
    [onRemove, attachment.id]
  );
  return (
    <Attachment data={attachment} onRemove={handleRemove}>
      <AttachmentPreview />
      <AttachmentRemove />
    </Attachment>
  );
});
AttachmentItem.displayName = "AttachmentItem";

/** 附件展示区（仅在有附件时渲染，inline 横向缩略图） */
const PromptInputAttachmentsDisplay = memo(() => {
  const attachments = usePromptInputAttachments();
  const handleRemove = useCallback(
    (id: string) => attachments.remove(id),
    [attachments]
  );
  if (attachments.files.length === 0) return null;
  return (
    <Attachments variant="inline">
      {attachments.files.map((attachment) => (
        <AttachmentItem
          key={attachment.id}
          attachment={attachment}
          onRemove={handleRemove}
        />
      ))}
    </Attachments>
  );
});
PromptInputAttachmentsDisplay.displayName = "PromptInputAttachmentsDisplay";

/**
 * 聊天输入区域（PromptInput 内部）。
 *
 * 结构参考 ai-elements prompt-input 官方示例：
 * - 附件展示拆为独立 <PromptInputAttachmentsDisplay>（在 Body 外，inline 缩略图）
 * - Body 仅放 Textarea
 * - Footer: 工具按钮（相册 / 拍照）+ Submit（status 接管 streaming/stop）
 *
 * 必须作为 <PromptInput> 的直接子节点渲染，以便通过 usePromptInputAttachments
 * 读取并操作附件。图片以 base64 data URL 形式随消息提交，对接后端
 * ChatRequest.images，适配 DashScope Qwen-VL 多模态接口。
 */
function ChatPromptInner({
  isStreaming,
  onStop,
}: {
  isStreaming: boolean;
  onStop: () => void;
}) {
  const attachments = usePromptInputAttachments();
  const cameraInputRef = useRef<HTMLInputElement | null>(null);

  const handleCameraChange = useCallback(
    (e: ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        attachments.add(e.target.files);
      }
      // 重置 value 允许重复选择同一文件
      e.target.value = "";
    },
    [attachments]
  );

  return (
    <>
      <PromptInputBody>
        <PromptInputTextarea placeholder="输入消息，或添加 / 拍摄图片提问…" />
      </PromptInputBody>
      <PromptInputFooter>
        <PromptInputTools>
          {/* 从相册 / 文件选择 */}
          <PromptInputActionMenu>
            <PromptInputActionMenuTrigger tooltip="添加图片" />
            <PromptInputActionMenuContent>
              <PromptInputActionAddAttachments label="从相册选择" />
            </PromptInputActionMenuContent>
          </PromptInputActionMenu>
          {/* 拍照：移动端 capture=environment 直接调起后置摄像头 */}
          <input
            ref={cameraInputRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={handleCameraChange}
            aria-label="拍照"
          />
          <PromptInputButton
            tooltip="拍照"
            onClick={() => cameraInputRef.current?.click()}
          >
            <CameraIcon className="size-4" />
          </PromptInputButton>
        </PromptInputTools>
        <PromptInputSubmit
          status={isStreaming ? "streaming" : "ready"}
          onStop={onStop}
        />
      </PromptInputFooter>
    </>
  );
}

export default function ChatPage() {
  const { currentThreadId, setThreadId, sidebarOpen, setSidebarOpen } = useChatStore();
  const { messages, sendMessage, stop, clearMessages, isStreaming, setMessages, usage, setUsage } =
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

  // 发送消息：支持文本 + 图片（图片以 base64 data URL 形式提交，后端走 image_analysis 意图链路）
  const handleSend = useCallback(
    async ({ text, files }: PromptInputMessage) => {
      const images = files
        .map((f) => f.url)
        .filter((u): u is string => typeof u === "string" && u.length > 0);
      const hasText = text.trim().length > 0;
      if (!hasText && images.length === 0) return;
      sendMessage(text, images);
    },
    [sendMessage]
  );

  // 加载指定线程的历史消息（恢复 thinking / toolCalls）
  const loadThreadMessages = useCallback(async (id: string) => {
    // 使用同源相对路径：dev 由 vite proxy 转发，prod 由后端同域托管，避免跨域
    const API_URL = "/api";
    const token = localStorage.getItem("fitcream_token");
    try {
      const res = await fetch(`${API_URL}/chat/threads/${id}/messages`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const json = await res.json();
        const data = json.data || {};
        const restored: ChatMessage[] = (data.messages || []).map(
          (m: {
            id: string;
            role: string;
            content: string | null;
            metadata_json?: {
              thinking?: string;
              tool_calls?: Array<{
                id: string;
                name: string;
                input: Record<string, unknown>;
                output?: unknown;
                status: string;
              }>;
            } | null;
            created_at: string;
          }) => ({
            id: m.id,
            role: m.role as "user" | "assistant",
            content: m.content || "",
            thinking: m.metadata_json?.thinking || undefined,
            toolCalls:
              m.metadata_json?.tool_calls?.map((tc) => ({
                id: tc.id,
                name: tc.name,
                input: tc.input,
                output: tc.output,
                status: (tc.status === "running"
                  ? "running"
                  : tc.status === "error"
                    ? "error"
                    : "completed") as "running" | "completed" | "error",
              })) || undefined,
            createdAt: new Date(m.created_at).getTime(),
          }),
        );
        setMessages(restored);
      }
    } catch {
      // ignore
    }
  }, [setMessages]);

  // 进入页面时若存在上次的会话线程，则自动恢复该对话（需求2）
  const restoredRef = useRef(false);
  useEffect(() => {
    if (restoredRef.current) return;
    restoredRef.current = true;
    const id = useChatStore.getState().currentThreadId;
    if (id) loadThreadMessages(id);
  }, [loadThreadMessages]);

  const handleSelectThread = (id: string) => {
    setThreadId(id);
    loadThreadMessages(id);
    setSidebarOpen(false);
    // 从 threads 列表中找到该线程的 totalTokens，初始化 usage
    const t = threads.find((th) => th.id === id);
    setUsage({
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: t?.totalTokens ?? 0,
    });
  };

  return (
    <AppLayout>
      <div className="relative flex h-full flex-col">
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
          <div className="flex items-center gap-2">
            <Context
              usedTokens={usage.total_tokens}
              maxTokens={MAX_CONTEXT_TOKENS}
              usage={{
                inputTokens: usage.input_tokens,
                outputTokens: usage.output_tokens,
                totalTokens: usage.total_tokens,
                inputTokenDetails: {
                  noCacheTokens: undefined,
                  cacheReadTokens: undefined,
                  cacheWriteTokens: undefined,
                },
                outputTokenDetails: {
                  textTokens: undefined,
                  reasoningTokens: undefined,
                },
              }}
            >
              <ContextTrigger className="h-8 gap-1.5 rounded-lg px-2.5 text-emerald-700 hover:bg-emerald-50" />
              <ContextContent side="bottom" align="end">
                <ContextContentHeader />
                <ContextContentBody className="space-y-1.5">
                  <ContextInputUsage />
                  <ContextOutputUsage />
                </ContextContentBody>
                <ContextContentFooter>
                  <span className="text-muted-foreground">上下文窗口</span>
                  <span>{MAX_CONTEXT_TOKENS.toLocaleString()} tokens</span>
                </ContextContentFooter>
              </ContextContent>
            </Context>
            <Link
              to="/knowledge-bases"
              title="知识库"
              className={cn(
                buttonVariants({ variant: "outline", size: "sm" }),
                "gap-1.5 rounded-lg border-emerald-200 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800"
              )}
            >
              <BookOpenIcon className="size-3.5" />
              <span className="hidden sm:inline">知识库</span>
            </Link>
            <Button
              onClick={handleNewChat}
              size="sm"
              variant="outline"
              className="gap-1.5 rounded-lg border-emerald-200 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800"
            >
              <PlusIcon className="size-4" />
              新对话
            </Button>
            <Button
              onClick={() => setSidebarOpen(!sidebarOpen)}
              size="sm"
              variant="outline"
              title="会话历史"
              className={`gap-1.5 rounded-lg border-emerald-200 text-emerald-700 hover:bg-emerald-50 hover:text-emerald-800 ${sidebarOpen ? "bg-emerald-50" : ""}`}
            >
              <HistoryIcon className="size-4" />
              <span className="hidden sm:inline">历史</span>
            </Button>
          </div>
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
          <PromptInputProvider>
            <PromptInput
              accept="image/*"
              multiple
              globalDrop
              maxFiles={MAX_IMAGE_FILES}
              maxFileSize={MAX_IMAGE_SIZE}
              onSubmit={handleSend}
              className="mx-auto max-w-3xl"
            >
              <PromptInputAttachmentsDisplay />
              <ChatPromptInner isStreaming={isStreaming} onStop={stop} />
            </PromptInput>
          </PromptInputProvider>
        </div>

        {/* 右侧会话历史抽屉 */}
        {sidebarOpen && (
          <div className="absolute inset-y-0 right-0 z-20 flex w-80 flex-col border-l border-emerald-100 bg-white/95 shadow-xl backdrop-blur">
            <div className="flex shrink-0 items-center justify-between border-b border-emerald-100 px-4 py-3">
              <span className="text-sm font-semibold text-emerald-900">会话历史</span>
              <button
                type="button"
                onClick={() => setSidebarOpen(false)}
                className="rounded-md p-1 text-emerald-500 hover:bg-emerald-50 hover:text-emerald-700"
              >
                <XIcon className="size-4" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-2">
              {threads.length === 0 ? (
                <p className="px-2 py-8 text-center text-xs text-emerald-600/60">
                  暂无历史会话
                </p>
              ) : (
                <ul className="space-y-1">
                  {threads.map((t) => (
                    <li key={t.id}>
                      <div
                        className={`group flex cursor-pointer flex-col gap-1 rounded-lg px-3 py-2.5 transition-colors ${
                          currentThreadId === t.id
                            ? "bg-emerald-100 text-emerald-900"
                            : "text-emerald-800 hover:bg-emerald-50"
                        }`}
                        onClick={() => handleSelectThread(t.id)}
                      >
                        <div className="flex items-center gap-2">
                          <span className="line-clamp-1 flex-1 text-sm font-medium">{t.title}</span>
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteThread(t.id);
                            }}
                            className="opacity-0 transition-opacity group-hover:opacity-100"
                          >
                            <Trash2Icon className="size-3.5 text-emerald-400 hover:text-red-500" />
                          </button>
                        </div>
                        <div className="flex items-center gap-3 text-[11px] text-emerald-500/70">
                          <span className="flex items-center gap-0.5">
                            <ZapIcon className="size-3" />
                            {t.totalTokens > 0 ? `${(t.totalTokens / 1000).toFixed(1)}k tokens` : "0 tokens"}
                          </span>
                          <span>{t.messageCount} 条消息</span>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
