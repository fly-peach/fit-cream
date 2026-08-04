import { memo, useCallback, useEffect, useLayoutEffect, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useStickToBottomContext } from "use-stick-to-bottom";
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
import { MemoryPanel } from "@/components/memory-panel";
import { ThreadHistoryItem } from "@/components/thread-history-item";
import { ToolCallCard } from "@/components/tool-call-card";
import { Button, buttonVariants } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { api, checkAuthEnvelope } from "@/lib/api";
import {
  PlusIcon,
  BotMessageSquareIcon,
  HistoryIcon,
  XIcon,
  CameraIcon,
  BookOpenIcon,
  BrainIcon,
  LoaderCircleIcon,
} from "lucide-react";
import type { ChatMessage, ToolCall } from "@/types/chat";

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

/**
 * 链式思考渲染：按 thinkingOffset 把工具块插入到思考文本流中。
 *
 * 当工具调用没有 offset 信息（历史消息兼容）时，回退到旧布局：
 * 思考文本在上，工具块在下。
 */
function InterleavedReasoning({
  thinking,
  toolCalls,
}: {
  thinking?: string;
  toolCalls?: ToolCall[];
}) {
  if (!toolCalls?.length) {
    return thinking ? <div className="whitespace-pre-wrap">{thinking}</div> : null;
  }

  const hasOffsets = toolCalls.some((tc) => typeof tc.thinkingOffset === "number");
  if (!hasOffsets) {
    return (
      <>
        {thinking && <div className="whitespace-pre-wrap">{thinking}</div>}
        <div className={thinking ? "mt-3 space-y-2 border-t border-border/50 pt-3" : "space-y-2"}>
          {toolCalls.map((tc) => (
            <ToolCallCard key={tc.id} tc={tc} />
          ))}
        </div>
      </>
    );
  }

  const sorted = [...toolCalls].sort(
    (a, b) => (a.thinkingOffset ?? 0) - (b.thinkingOffset ?? 0)
  );
  const nodes: ReactNode[] = [];
  let lastOffset = 0;

  for (const tc of sorted) {
    const offset = Math.min(tc.thinkingOffset ?? 0, thinking?.length ?? 0);
    if (thinking && lastOffset < offset) {
      nodes.push(
        <div key={`thinking-${lastOffset}`} className="whitespace-pre-wrap">
          {thinking.slice(lastOffset, offset)}
        </div>
      );
    }
    nodes.push(<ToolCallCard key={`tool-${tc.id}`} tc={tc} />);
    lastOffset = offset;
  }

  if (thinking && lastOffset < thinking.length) {
    nodes.push(
      <div key="thinking-end" className="whitespace-pre-wrap">
        {thinking.slice(lastOffset)}
      </div>
    );
  }

  return <div className="space-y-2">{nodes}</div>;
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
              <InterleavedReasoning
                thinking={message.thinking}
                toolCalls={message.toolCalls}
              />
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

/** 历史消息分页大小：首屏仅加载最近 10 条，向上滚动再加载更早的分页 */
const HISTORY_PAGE_SIZE = 10;

/** 后端 /chat/threads/{id}/messages 返回的原始消息行 */
interface HistoryMessageRow {
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
      thinking_offset?: number;
    }>;
  } | null;
  created_at: string;
}

/** 将后端消息行还原为前端 ChatMessage（恢复 thinking / toolCalls） */
function restoreMessage(m: HistoryMessageRow): ChatMessage {
  return {
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
        thinkingOffset: tc.thinking_offset ?? undefined,
      })) || undefined,
    createdAt: new Date(m.created_at).getTime(),
  };
}

/**
 * 历史消息向上加载哨兵（渲染在消息列表顶部）。
 *
 * - 通过 useStickToBottomContext 拿到滚动容器并上报给父组件（prepend 后锚定滚动位置用）
 * - IntersectionObserver 监测哨兵可见（提前 300px 预载），触发加载上一页
 */
function OlderMessagesLoader({
  hasMore,
  loading,
  onLoadOlder,
  onScrollEl,
}: {
  hasMore: boolean;
  loading: boolean;
  onLoadOlder: () => void;
  onScrollEl: (el: HTMLElement | null) => void;
}) {
  const { scrollRef } = useStickToBottomContext();
  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    onScrollEl(scrollRef.current);
    return () => onScrollEl(null);
  }, [scrollRef, onScrollEl]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    const root = scrollRef.current;
    if (!sentinel || !root || !hasMore) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) onLoadOlder();
      },
      { root, rootMargin: "300px 0px 0px 0px" }
    );
    io.observe(sentinel);
    return () => io.disconnect();
  }, [hasMore, onLoadOlder, scrollRef]);

  if (!hasMore) return null;
  return (
    <div ref={sentinelRef} className="flex h-6 shrink-0 items-center justify-center">
      {loading && <LoaderCircleIcon className="size-4 animate-spin text-emerald-400" />}
    </div>
  );
}

/** content_type -> 上传文件名后缀 */
const MIME_EXT: Record<string, string> = {
  "image/jpeg": ".jpg",
  "image/png": ".png",
  "image/webp": ".webp",
  "image/gif": ".gif",
};

/**
 * 将附件图片上传到后端 /chat/upload-image（转存阿里云 OSS），返回可访问 URL。
 *
 * 附件在提交时已被转为 base64 data URL，这里还原为 Blob 以 multipart 上传；
 * 后端优先返回 OSS 签名 URL（未配置 OSS 时回退 base64）。上传失败时抛错，
 * 由调用方决定是否回退到原始 data URL。传入 thread_id 时图片按会话归目录。
 */
async function uploadAttachmentImage(
  file: {
    url: string;
    mediaType?: string;
    filename?: string;
  },
  threadId?: string | null
): Promise<string> {
  const blob = await (await fetch(file.url)).blob();
  const mime = file.mediaType || blob.type || "image/jpeg";
  const ext = MIME_EXT[mime] ?? ".jpg";
  const filename = file.filename || `upload${ext}`;
  const fd = new FormData();
  fd.append("file", blob, filename);
  if (threadId) fd.append("thread_id", threadId);
  const data = await api.upload<{ url: string }>("/chat/upload-image", fd);
  return data.url;
}

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
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const { currentThreadId, setThreadId, sidebarOpen, setSidebarOpen } = useChatStore();
  const { threads, loadThreads, deleteThread, renameThread } = useThreads();
  const { messages, sendMessage, stop, clearMessages, isStreaming, setMessages, usage, seedUsage } =
    useChatSSE(currentThreadId, loadThreads);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [tab, setTab] = useState<"chat" | "memories">("chat");

  // ---- 历史消息分页（首屏最近 10 条，向上滚动加载更早分页） ----
  /** 是否还有更早的消息可加载 */
  const [hasMore, setHasMore] = useState(false);
  /** 正在加载更早分页 */
  const [loadingOlder, setLoadingOlder] = useState(false);
  /** 下一个要加载的更早分页页码（0 表示没有更多） */
  const nextOlderPageRef = useRef(0);
  /** 当前已加载消息所属线程（快速切换会话时丢弃过期响应） */
  const loadedThreadIdRef = useRef<string | null>(null);
  /** 防止并发触发加载上一页 */
  const loadingOlderRef = useRef(false);
  /** 滚动容器（StickToBottom 内部 scroll element，由 OlderMessagesLoader 上报） */
  const scrollElRef = useRef<HTMLElement | null>(null);
  /** prepend 旧消息前的滚动度量，用于渲染后恢复视口锚点 */
  const scrollMetricsRef = useRef<{ height: number; top: number } | null>(null);
  /** prepend 后跳过一次"滚动到底部"，避免把用户拽回底部 */
  const skipBottomScrollRef = useRef(false);

  const handleScrollEl = useCallback((el: HTMLElement | null) => {
    scrollElRef.current = el;
  }, []);

  // 已 seed usage 的会话 id：仅真正切换到新会话时重置 usage，
  // 同一会话内 threads 列表刷新不应覆盖实时累计值
  const seededThreadRef = useRef<string | null>(null);

  const seedUsageForThread = useCallback(
    (id: string) => {
      if (seededThreadRef.current === id) return;
      seededThreadRef.current = id;
      const t = threads.find((th) => th.id === id);
      seedUsage(id, {
        input_tokens: 0,
        output_tokens: 0,
        total_tokens: t?.totalTokens ?? 0,
      });
    },
    [threads, seedUsage]
  );

  useEffect(() => {
    if (skipBottomScrollRef.current) {
      skipBottomScrollRef.current = false;
      return;
    }
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // prepend 旧消息后恢复视口锚点：保持用户正在看的内容不动
  useLayoutEffect(() => {
    const metrics = scrollMetricsRef.current;
    if (!metrics) return;
    scrollMetricsRef.current = null;
    const el = scrollElRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight - metrics.height + metrics.top;
  }, [messages]);

  const handleNewChat = () => {
    seededThreadRef.current = null;
    loadedThreadIdRef.current = null;
    nextOlderPageRef.current = 0;
    setHasMore(false);
    setThreadId(null);
    clearMessages();
    setTab("chat");
  };

  // 发送消息：支持文本 + 图片。图片先经后端转存阿里云 OSS（返回签名 URL），
  // 再以 URL 形式提交，后端走 image_analysis 意图链路（DashScope Qwen-VL）。
  const handleSend = useCallback(
    async ({ text, files }: PromptInputMessage) => {
      const attachments = files.filter(
        (f) => typeof f.url === "string" && f.url.length > 0
      );
      const hasText = text.trim().length > 0;
      if (!hasText && attachments.length === 0) return;

      // 逐张上传至 OSS；单张失败回退原始 data URL，保证消息仍可发送
      const threadId = useChatStore.getState().currentThreadId;
      const images = await Promise.all(
        attachments.map(async (f) => {
          try {
            return await uploadAttachmentImage(f, threadId);
          } catch {
            return f.url;
          }
        })
      );

      sendMessage(text, images);
    },
    [sendMessage]
  );

  // 加载指定线程的历史消息：仅取最近一页（10 条），更早的由向上滚动按需加载。
  // 后端按 created_at 升序 + offset 分页，最后一页即最新消息。
  const loadThreadMessages = useCallback(async (id: string) => {
    // 使用同源相对路径：dev 由 vite proxy 转发，prod 由后端同域托管，避免跨域
    const API_URL = "/api";
    loadedThreadIdRef.current = id;
    nextOlderPageRef.current = 0;
    setHasMore(false);
    try {
      // 首页请求顺带拿 total；消息数不超过一页时它就是完整消息列表
      const res = await fetch(
        `${API_URL}/chat/threads/${id}/messages?page=1&size=${HISTORY_PAGE_SIZE}`
      );
      if (!res.ok) return;
      const json = await res.json();
      checkAuthEnvelope(json);
      const data = json.data || {};
      const total: number = typeof data.total === "number" ? data.total : 0;
      const lastPage = Math.max(1, Math.ceil(total / HISTORY_PAGE_SIZE));
      let rows: HistoryMessageRow[] = data.messages || [];
      if (lastPage > 1) {
        const res2 = await fetch(
          `${API_URL}/chat/threads/${id}/messages?page=${lastPage}&size=${HISTORY_PAGE_SIZE}`
        );
        if (res2.ok) {
          const json2 = await res2.json();
          checkAuthEnvelope(json2);
          rows = json2.data?.messages || [];
        }
      }
      // 快速切换会话时丢弃过期响应
      if (loadedThreadIdRef.current !== id) return;
      setMessages(rows.map(restoreMessage));
      nextOlderPageRef.current = lastPage - 1;
      setHasMore(lastPage > 1);
    } catch {
      // ignore
    }
  }, [setMessages]);

  // 向上滚动加载更早的一页消息，prepend 到列表头部并锚定滚动位置
  const loadOlder = useCallback(async () => {
    const id = loadedThreadIdRef.current;
    const page = nextOlderPageRef.current;
    if (!id || page < 1 || loadingOlderRef.current) return;
    loadingOlderRef.current = true;
    setLoadingOlder(true);
    try {
      const res = await fetch(
        `/api/chat/threads/${id}/messages?page=${page}&size=${HISTORY_PAGE_SIZE}`
      );
      if (!res.ok) return;
      const json = await res.json();
      checkAuthEnvelope(json);
      if (loadedThreadIdRef.current !== id) return;
      const rows: HistoryMessageRow[] = json.data?.messages || [];
      nextOlderPageRef.current = page - 1;
      setHasMore(page - 1 >= 1);
      if (rows.length > 0) {
        const el = scrollElRef.current;
        if (el) {
          scrollMetricsRef.current = { height: el.scrollHeight, top: el.scrollTop };
        }
        skipBottomScrollRef.current = true;
        setMessages((prev) => [...rows.map(restoreMessage), ...prev]);
      }
    } catch {
      // ignore
    } finally {
      loadingOlderRef.current = false;
      setLoadingOlder(false);
    }
  }, [setMessages]);

  // 进入页面恢复：URL 会话优先；无 URL 参数时恢复上次会话（保留旧行为）。
  // 仅负责加载目标会话消息，seed usage 交由下方 effect 等待 threads 列表就绪后执行
  const initRef = useRef(false);
  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    const id = sessionId ?? currentThreadId;
    if (!id) return;
    setThreadId(id);
    loadThreadMessages(id);
  }, [sessionId, currentThreadId, setThreadId, loadThreadMessages]);

  // 目标会话确定且 threads 列表加载完成（能拿到历史 totalTokens）后，seed usage 一次
  useEffect(() => {
    const id = sessionId ?? currentThreadId;
    if (!id) return;
    const t = threads.find((th) => th.id === id);
    if (!t) return;
    seedUsageForThread(id);
  }, [sessionId, currentThreadId, threads, seedUsageForThread]);

  // store → URL：新会话创建（SSE start 返回 thread_id）或新对话时同步地址栏
  useEffect(() => {
    if (currentThreadId && currentThreadId !== sessionId) {
      navigate(`/chat/${currentThreadId}`, { replace: true });
    } else if (!currentThreadId && sessionId) {
      navigate("/chat", { replace: true });
    }
  }, [currentThreadId, sessionId, navigate]);

  // URL → store：点击历史会话 / 直接访问 / 前进后退时恢复对应会话
  const prevSessionRef = useRef<string | undefined>(sessionId);
  useEffect(() => {
    if (sessionId === prevSessionRef.current) return;
    prevSessionRef.current = sessionId;
    if (!sessionId || sessionId === currentThreadId) return;
    setThreadId(sessionId);
    loadThreadMessages(sessionId);
    seedUsageForThread(sessionId);
  }, [sessionId, currentThreadId, threads, setThreadId, loadThreadMessages, seedUsageForThread]);

  const handleSelectThread = (id: string) => {
    setThreadId(id);
    loadThreadMessages(id);
    setSidebarOpen(false);
    // 真正切换到新会话时才用该会话历史累计值重置 usage（seedUsage 内部有切换守卫）
    seedUsageForThread(id);
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

        <div className="flex shrink-0 items-center border-b border-emerald-100 bg-white/50 px-4 py-1.5">
          <Tabs
            value={tab}
            onValueChange={(v) => setTab(v as "chat" | "memories")}
          >
            <TabsList className="bg-emerald-50">
              <TabsTrigger value="chat">对话</TabsTrigger>
              <TabsTrigger value="memories" className="gap-1.5">
                <BrainIcon className="size-3.5" />
                我的记忆
              </TabsTrigger>
            </TabsList>
          </Tabs>
        </div>

        {tab === "chat" ? (
          <>
        <Conversation className="flex-1">
          <ConversationContent>
            <OlderMessagesLoader
              hasMore={hasMore}
              loading={loadingOlder}
              onLoadOlder={loadOlder}
              onScrollEl={handleScrollEl}
            />
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
                      <ThreadHistoryItem
                        thread={t}
                        isActive={currentThreadId === t.id}
                        isEditing={editingThreadId === t.id}
                        onSelect={() => handleSelectThread(t.id)}
                        onDelete={() => {
                          if (currentThreadId === t.id) handleNewChat();
                          deleteThread(t.id);
                        }}
                        onStartEdit={() => setEditingThreadId(t.id)}
                        onCancelEdit={() => setEditingThreadId(null)}
                        onRename={async (title) => {
                          const ok = await renameThread(t.id, title);
                          setEditingThreadId(null);
                          return ok;
                        }}
                      />
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}
          </>
        ) : (
          <MemoryPanel />
        )}
      </div>
    </AppLayout>
  );
}
