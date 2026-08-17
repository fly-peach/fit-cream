import { memo, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ChangeEvent, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useStickToBottomContext } from "use-stick-to-bottom";
import { Camera, CameraDirection } from "@capacitor/camera";
import { Capacitor } from "@capacitor/core";
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
  Plan,
  PlanContent,
  PlanDescription,
  PlanHeader,
  PlanTitle,
  PlanTrigger,
} from "@/components/ai-elements/plan";
import {
  Confirmation,
  ConfirmationAccepted,
  ConfirmationAction,
  ConfirmationActions,
  ConfirmationRejected,
  ConfirmationTitle,
} from "@/components/ai-elements/confirmation";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FormCard } from "@/components/form-card";
import { DayDesignCard } from "@/components/day-design-card";
import { PlanQueuePanel } from "@/components/plan-queue-panel";
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
import { toolNameMap } from "@/components/tool-meta";
import type { PlanQueue } from "@/types/chat";
import { Button, buttonVariants } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { api, API_URL, checkAuthEnvelope } from "@/lib/api";
import {
  PlusIcon,
  BotMessageSquareIcon,
  HistoryIcon,
  XIcon,
  CameraIcon,
  BookOpenIcon,
  BrainIcon,
  DumbbellIcon,
  LoaderCircleIcon,
} from "lucide-react";
import type { AgentStep, ChatMessage, ToolApproval, ToolCall } from "@/types/chat";

/**
 * 清理模型回复中误以纯文本形式输出的工具调用标记。
 *
 * 部分模型会把工具调用以 `[调用 xxx(...)]` / `【调用 xxx】` 的文本写进 content，
 * 而真正的工具调用已由 Tool 组件单独渲染，这里需要把这类文本剔除，避免重复且难看。
 */
function cleanContent(text: string): string {
  if (!text) return "";
  return text
    .replace(/[[【]\s*调用\s*[^\]】]*[\]】]/g, "")
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
        <div className={thinking ? "mt-2 space-y-1.5 border-t border-border/50 pt-2" : "space-y-1.5"}>
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

function MessageItem({
  message,
  pendingApproval,
  onResume,
  isLastAssistant,
  onSubmitForm,
}: {
  message: ChatMessage;
  pendingApproval?: { messageId: string } | null;
  onResume?: (decisions: { type: "approve" | "reject"; reason?: string }[]) => void;
  /** 是否为最新一条助手消息（仅此消息上的表单卡可交互） */
  isLastAssistant?: boolean;
  onSubmitForm?: (text: string) => void;
}) {
  if (message.role === "user") {
    const hasImages = !!message.images && message.images.length > 0;
    const hasText = !!message.content && message.content !== "[图片消息]";
    return (
      <Message from="user">
        <MessageContent>
          {hasImages && (
            <div className="mb-2 flex flex-wrap justify-end gap-2">
              {message.images!.map((url, i) => (
                <ChatImage key={i} url={url} alt={`图片 ${i + 1}`} />
              ))}
            </div>
          )}
          {hasText && <MessageResponse>{message.content}</MessageResponse>}
        </MessageContent>
      </Message>
    );
  }

  // 过滤模型误输出的工具调用文本
  const cleaned = cleanContent(message.content);
  const hasThinking = !!message.thinking;
  const hasToolCalls = !!message.toolCalls?.length;
  // 新格式：steps 步骤流优先直接平铺；无 steps 时回退旧 thinking+toolCalls 折叠块
  const hasSteps = !!message.steps?.length;
  const showLegacyReasoning = !hasSteps && (hasThinking || hasToolCalls);
  const isThinking = message.isStreaming && !message.content;

  // 仅最新助手消息上的表单可交互；流式中禁止提交（sendMessage 会被拦截）
  const formInteractive = !!isLastAssistant && !message.isStreaming && !!onSubmitForm;

  // present_plan_tool 步骤单独渲染为 Plan 卡片（不进思考时间线）
  const planSteps = (message.steps || []).filter(
    (s) => s.type === "tool" && s.tool === "present_plan_tool"
  );
  // 修改时预填的计划正文：取最近一个 present_plan_tool 的 content
  const planContent = planSteps.length
    ? ((planSteps[planSteps.length - 1].input || {}) as { content?: string }).content
    : undefined;

  const approvals = message.approvals || [];
  const interactive = !!pendingApproval && pendingApproval.messageId === message.id && !!onResume;

  return (
    <Message from="assistant">
      <MessageContent>
        {/* 新格式：扁平时间流（思考→回复→工具 交错渲染） */}
        {hasSteps && (
          <StreamSteps
            steps={message.steps!}
            isStreaming={message.isStreaming}
            fallbackContent={cleaned}
            formInteractive={formInteractive}
            onSubmitForm={onSubmitForm}
          />
        )}

        {/* 旧格式降级：保持原折叠块 */}
        {!hasSteps && showLegacyReasoning && (
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

        {/* HITL 审批卡片 */}
        {approvals.map((a, i) => (
          <ApprovalCard
            key={`approval-${a.id || i}`}
            approval={a}
            interactive={interactive}
            planContent={planContent}
            onApprove={() => onResume?.([{ type: "approve" }])}
            onReject={() => onResume?.([{ type: "reject" }])}
            onEdit={(text) => onResume?.([{ type: "reject", reason: text }])}
          />
        ))}

        {/* 旧格式（无 steps）的正文 */}
        {!hasSteps && cleaned && <MessageResponse>{cleaned}</MessageResponse>}

        {message.isStreaming && !message.content && !hasSteps && !showLegacyReasoning && (
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
const HISTORY_PAGE_SIZE = 8;

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
    images?: string[];
    steps?: AgentStep[];
    approvals?: Array<{
      id: string;
      tool: string;
      input: Record<string, unknown>;
      description?: string;
      allowed_decisions?: string[];
      state: string;
      approved?: boolean;
      decision?: string;
    }>;
    approval_state?: string;
  } | null;
  created_at: string;
}

/** 历史消息图片：加载失败（签名 URL 过期等）时回退为占位提示 */
function ChatImage({ url, alt }: { url: string; alt: string }) {
  const [failed, setFailed] = useState(false);
  if (failed) {
    return (
      <div className="flex h-24 w-40 items-center justify-center rounded-lg border border-dashed border-border/70 bg-muted/40 text-center text-xs text-muted-foreground">
        图片已过期
      </div>
    );
  }
  return (
    <img
      src={url}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className="max-h-52 rounded-lg border border-emerald-100 object-cover shadow-sm"
    />
  );
}

/** 将后端消息行还原为前端 ChatMessage（恢复 thinking / toolCalls / images） */
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
    images: m.metadata_json?.images,
    steps: m.metadata_json?.steps,
    approvals: m.metadata_json?.approvals?.map((a) => ({
      id: a.id,
      tool: a.tool,
      input: a.input || {},
      description: a.description,
      allowedDecisions: a.allowed_decisions || ["approve", "reject"],
      state: (a.state === "output-available" || a.state === "output-denied" || a.state === "approval-responded"
        ? a.state
        : "approval-responded") as ToolApproval["state"],
      approved: a.approved,
      decision: a.decision as "approve" | "reject" | undefined,
    })),
    createdAt: new Date(m.created_at).getTime(),
  };
}

/** 把 AgentStep 的 tool 步骤适配为 ToolCall，复用现有 ToolCallCard 渲染 */
function toolCallFromStep(step: AgentStep): ToolCall {
  return {
    id: step.id || "",
    name: step.tool || "unknown",
    input: step.input || {},
    output: step.output,
    status: step.status || "completed",
    error: undefined,
  };
}

/**
 * ReAct 步骤流：ChainOfThought 时间线渲染（思考段 + 工具步骤交错）。
 *
 * - 默认展开；流式结束 1s 后自动折叠一次（历史消息保持展开）
 * - thought 步骤：BrainIcon + 思考文本；流式中最新一段标记 active
 * - tool 步骤：工具图标 + 中文名 + 运行态 spinner，结果正文以 embedded
 *   ToolCallCard 嵌入步骤 children（无卡片外壳，避免与节点头部重复）
 */
/**
 * 扁平时间流渲染：把 ReAct 步骤序列按真实顺序交错展示
 * （思考▸ → 回复 → 工具卡 → 思考▸ → … → 最终回复），
 * 表单/计划在原位渲染。历史消息（steps 无 reply）时用 fallbackContent 兜底正文。
 */
function StreamSteps({
  steps,
  isStreaming,
  fallbackContent,
  formInteractive,
  onSubmitForm,
}: {
  steps: AgentStep[];
  isStreaming?: boolean;
  fallbackContent?: string;
  formInteractive?: boolean;
  onSubmitForm?: (text: string) => void;
}) {
  const hasReply = steps.some((s) => s.type === "reply");
  return (
    <div className="space-y-2">
      {steps.map((step, i) => {
        if (step.type === "thought") {
          if (!step.content) return null;
          return (
            <Reasoning key={i} isStreaming={isStreaming && i === steps.length - 1}>
              <ReasoningTrigger />
              <ReasoningContent>{step.content}</ReasoningContent>
            </Reasoning>
          );
        }
        if (step.type === "reply") {
          if (!step.content) return null;
          return (
            <div key={i} className="leading-relaxed">
              <MessageResponse>{step.content}</MessageResponse>
            </div>
          );
        }
        if (step.type === "tool") {
          const tool = step.tool || "unknown";
          if (tool === "present_form_tool") {
            return (
              <FormCard
                key={step.id || i}
                step={step}
                interactive={!!formInteractive}
                onSubmit={(text) => onSubmitForm?.(text)}
              />
            );
          }
          if (tool === "present_plan_tool") {
            return <PlanCard key={step.id || i} step={step} />;
          }
          if (tool === "present_day_design_tool") {
            return (
              <DayDesignCard
                key={step.id || i}
                step={step}
                interactive={!!formInteractive}
                onSubmit={(text) => onSubmitForm?.(text)}
              />
            );
          }
          // 队列工具只驱动顶部待办面板，不在消息流内渲染卡片
          if (
            tool === "present_plan_queue_tool" ||
            tool === "update_plan_queue_item_tool"
          ) {
            return null;
          }
          return <ToolCallCard key={step.id || i} tc={toolCallFromStep(step)} />;
        }
        return null;
      })}
      {/* 历史兼容：steps 无 reply 步骤（旧消息/旧后端）时，追加 message.content 作为正文 */}
      {!hasReply && fallbackContent && (
        <div className="leading-relaxed">
          <MessageResponse>{fallbackContent}</MessageResponse>
        </div>
      )}
      {isStreaming && (
        <span className="inline-block h-3 w-1 animate-pulse bg-muted-foreground/40" />
      )}
    </div>
  );
}

/** 计划提案中的单项数据变更（present_plan_tool.changes） */
interface PlanChange {
  domain?: string;
  action?: string;
  target?: string;
  detail?: string;
}

/**
 * 计划提案卡片：把 present_plan_tool 步骤渲染为可折叠 Plan 卡片。
 * title/description/content/changes 取自工具入参；running 时标题/摘要 shimmer。
 * changes 渲染为「即将执行的数据变更」总览表格，用户审批前的最后确认依据。
 */
function PlanCard({ step }: { step: AgentStep }) {
  const input = (step.input || {}) as {
    title?: string;
    description?: string;
    content?: string;
    changes?: PlanChange[];
  };
  const streaming = step.status === "running";
  const changes = Array.isArray(input.changes) ? input.changes : [];
  return (
    <Plan isStreaming={streaming} defaultOpen={streaming}>
      <PlanHeader>
        <div className="flex flex-col gap-0.5">
          <PlanTitle>{input.title || "计划提案"}</PlanTitle>
          {input.description ? <PlanDescription>{input.description}</PlanDescription> : null}
        </div>
        <PlanTrigger />
      </PlanHeader>
      <PlanContent>
        {changes.length > 0 && (
          <div className="mb-3 overflow-x-auto rounded-lg border border-emerald-200">
            <div className="border-b border-emerald-100 bg-emerald-50/60 px-3 py-2 text-xs font-semibold text-emerald-900">
              即将执行的数据变更
            </div>
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-emerald-100 bg-emerald-50/30 text-left text-emerald-800/70">
                  <th className="px-3 py-1.5 font-medium">范围</th>
                  <th className="px-3 py-1.5 font-medium">操作</th>
                  <th className="px-3 py-1.5 font-medium">对象</th>
                  <th className="px-3 py-1.5 font-medium">说明</th>
                </tr>
              </thead>
              <tbody>
                {changes.map((c, i) => (
                  <tr key={i} className="border-b border-emerald-50 last:border-0">
                    <td className="px-3 py-1.5 text-emerald-900">{c.domain || "—"}</td>
                    <td className="px-3 py-1.5">
                      <span className="rounded bg-emerald-100 px-1.5 py-0.5 font-medium text-emerald-700">
                        {c.action || "—"}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-emerald-900">{c.target || "—"}</td>
                    <td className="px-3 py-1.5 text-muted-foreground">{c.detail || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="bg-emerald-50/40 px-3 py-1.5 text-[11px] text-emerald-700/80">
              确认无误后点击下方「批准」，我就开始为你部署计划
            </div>
          </div>
        )}
        <MessageResponse>{input.content || ""}</MessageResponse>
      </PlanContent>
    </Plan>
  );
}

/**
 * HITL 审批卡片：用 Confirmation 组件呈现审批请求与结果。
 * - approval-requested 且 interactive（当前待审批消息）：显示批准/拒绝/修改按钮
 * - 已响应态：ConfirmationAccepted/Rejected 展示结果（历史消息只读，无按钮）
 * - 修改：textarea 预填计划正文，提交即 reject + 修订稿，agent 重新提案
 */
function ApprovalCard({
  approval,
  interactive,
  planContent,
  onApprove,
  onReject,
  onEdit,
}: {
  approval: ToolApproval;
  interactive: boolean;
  planContent?: string;
  onApprove: () => void;
  onReject: () => void;
  onEdit: (text: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [editText, setEditText] = useState("");
  const state = approval.state as
    | "approval-requested"
    | "approval-responded"
    | "output-available"
    | "output-denied";
  const toolName = toolNameMap[approval.tool] ?? approval.tool;
  const showActions = interactive && state === "approval-requested" && !editing;

  const startEdit = () => {
    setEditText(planContent || "");
    setEditing(true);
  };
  const submitEdit = () => {
    const text = editText.trim();
    if (!text) return;
    onEdit(text);
    setEditing(false);
  };

  return (
    <Confirmation
      approval={{ id: approval.id, approved: approval.approved }}
      state={state}
      className="border-emerald-200 bg-emerald-50/40"
    >
      <ConfirmationTitle>
        {state === "approval-requested" ? `需要确认：${toolName}` : toolName}
      </ConfirmationTitle>
      {showActions && (
        <ConfirmationActions>
          <ConfirmationAction onClick={onApprove}>批准</ConfirmationAction>
          <ConfirmationAction variant="outline" onClick={onReject}>
            拒绝
          </ConfirmationAction>
          <ConfirmationAction variant="outline" onClick={startEdit}>
            修改
          </ConfirmationAction>
        </ConfirmationActions>
      )}
      {interactive && state === "approval-requested" && editing && (
    <div className="space-y-1.5">
          <Textarea
            value={editText}
            onChange={(e) => setEditText(e.target.value)}
            rows={6}
            placeholder="修改后的计划方案…"
            className="bg-white text-sm"
          />
          <ConfirmationActions>
            <ConfirmationAction onClick={submitEdit}>提交修改</ConfirmationAction>
            <ConfirmationAction variant="outline" onClick={() => setEditing(false)}>
              取消
            </ConfirmationAction>
          </ConfirmationActions>
        </div>
      )}
      <ConfirmationAccepted>已批准</ConfirmationAccepted>
      <ConfirmationRejected>已拒绝</ConfirmationRejected>
    </Confirmation>
  );
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
/**
 * 「为我设计健身计划」确认弹窗：说明信息收集流程与隐私边界，
 * 确认后发送指令消息触发 plan_creation 意图 + plan-creation skill 全流程。
 */
function DesignPlanDialog({
  open,
  onOpenChange,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-emerald-950">
            <DumbbellIcon className="size-4 text-emerald-600" />
            为我设计健身计划
          </DialogTitle>
          <DialogDescription asChild>
            <div className="space-y-3 text-sm">
              <p>
                我会基于你的个人情况，设计一份科学、安全、有效的训练计划（可选配饮食计划）。
                开始前，我会通过几张表单卡片收集你的信息：
              </p>
              <div className="grid grid-cols-1 gap-1.5 rounded-lg bg-emerald-50/60 p-3 text-xs text-emerald-900">
                <span>📋 目标与动机 —— 想达到什么效果、期望多久达成</span>
                <span>🏥 健康与安全 —— 病史、伤病、用药（关乎运动安全，必需）</span>
                <span>💪 当前体能水平 —— 心肺、力量、训练经验</span>
                <span>🏃 运动经历 —— 训练频率、类型偏好、过往成果</span>
                <span>💡 生活方式 —— 作息、饮食、睡眠、可用器械与时间</span>
              </div>
              <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
                <li>你档案中已有的信息会直接复用，不会重复询问</li>
                <li>缺失的基础数据（身高/体重等）请通过表单补充</li>
                <li>收集完成后我会先展示计划提案与变更清单，经你确认才会保存</li>
              </ul>
              <p className="rounded-lg border border-emerald-100 bg-white px-3 py-2 text-xs text-emerald-700">
                🔒 隐私说明：身高、体重等基础数据会存入你的档案；
                病史、用药、睡眠等敏感信息仅用于本次计划设计，不会保存。
              </p>
            </div>
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            取消
          </Button>
          <Button
            onClick={onConfirm}
            className="bg-emerald-600 text-white hover:bg-emerald-700"
          >
            开始设计
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ChatPromptInner({
  isStreaming,
  onStop,
  onDesignPlan,
  kbEnabled,
  onToggleKb,
}: {
  isStreaming: boolean;
  onStop: () => void;
  onDesignPlan: () => void;
  kbEnabled: boolean;
  onToggleKb: () => void;
}) {
  const attachments = usePromptInputAttachments();
  const cameraInputRef = useRef<HTMLInputElement | null>(null);

  const isMobile = useMemo(
    () =>
      Capacitor.isNativePlatform() ||
      (typeof window !== "undefined" &&
        window.matchMedia("(pointer: coarse)").matches),
    []
  );

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

  const handleCameraClick = useCallback(async () => {
    if (!Capacitor.isNativePlatform()) {
      cameraInputRef.current?.click();
      return;
    }
    try {
      const photo = await Camera.takePhoto({
        quality: 90,
        correctOrientation: true,
        cameraDirection: CameraDirection.Rear,
      });
      if (!photo.webPath) {
        return;
      }
      const response = await fetch(photo.webPath);
      const blob = await response.blob();
      const file = new File([blob], `camera-${Date.now()}.jpg`, {
        type: blob.type || "image/jpeg",
      });
      attachments.add([file]);
    } catch {
      return;
    }
  }, [attachments]);

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
          {/* 拍照：仅移动端展示（App 用 Camera.takePhoto，移动浏览器用 capture 调起后置摄像头） */}
          {isMobile && (
            <>
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
                onClick={handleCameraClick}
              >
                <CameraIcon className="size-4" />
              </PromptInputButton>
            </>
          )}
          {/* 知识库回答开关（toggle）：开启后本轮优先检索用户订阅的知识库作答（全局偏好，localStorage 持久化，默认关闭）。
              Switch 必须放在按钮外：Base UI Switch 点击时会向隐藏 input 派发冒泡 click，
              嵌在按钮内会再次触发按钮 onClick 导致一次点击翻转两次（视觉上开关无效） */}
          <PromptInputButton
            tooltip="知识库回答"
            onClick={onToggleKb}
            aria-pressed={kbEnabled}
            className={cn(
              "gap-1.5 px-2",
              kbEnabled
                ? "text-emerald-700 hover:text-emerald-800"
                : "text-muted-foreground"
            )}
          >
            <BookOpenIcon className="size-4" />
            <span className="hidden text-xs md:inline">知识库回答</span>
          </PromptInputButton>
          <Switch
            size="sm"
            checked={kbEnabled}
            onCheckedChange={onToggleKb}
            aria-label="知识库回答开关"
            className={cn("ml-0.5", kbEnabled && "!bg-emerald-600")}
          />
          {/* 一键进入计划设计流程（弹窗确认后触发 plan_creation） */}
          <PromptInputButton
            tooltip="为我设计健身计划"
            onClick={onDesignPlan}
            className="gap-1 px-2 text-emerald-700 hover:text-emerald-800"
          >
            <DumbbellIcon className="size-4" />
            <span className="hidden text-xs md:inline">为我设计健身计划</span>
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
  // 知识库回答开关：全局偏好，localStorage 持久化（"1"=开启），默认关闭。
  // 生效值剔除计划设计线程（plan_design 流程不受开关影响）
  const [kbEnabled, setKbEnabled] = useState(() => {
    try {
      return localStorage.getItem("fitcream.kb-enabled") === "1";
    } catch {
      return false;
    }
  });
  const handleToggleKb = useCallback(() => {
    setKbEnabled((prev) => {
      const next = !prev;
      try {
        if (next) localStorage.setItem("fitcream.kb-enabled", "1");
        else localStorage.removeItem("fitcream.kb-enabled");
      } catch {
        // ignore
      }
      return next;
    });
  }, []);
  const kbEffective =
    kbEnabled &&
    !threads.some((t) => t.id === currentThreadId && t.agentMode === "plan_design");
  const { messages, sendMessage, stop, resume, clearMessages, isStreaming, setMessages, usage, compressionCount, seedUsage, pendingApproval } =
    useChatSSE(currentThreadId, loadThreads, kbEffective);
  const bottomRef = useRef<HTMLDivElement>(null);
  const [editingThreadId, setEditingThreadId] = useState<string | null>(null);
  const [tab, setTab] = useState<"chat" | "memories">("chat");
  const [conversationKey, setConversationKey] = useState(0);
  const [designPlanOpen, setDesignPlanOpen] = useState(false);

  // 最新一条助手消息 id：仅此消息上的表单卡可交互（提交后新消息追加即转只读）
  const lastAssistantId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant") return messages[i].id;
    }
    return null;
  }, [messages]);

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

  const handleNewChat = useCallback(() => {
    seededThreadRef.current = null;
    loadedThreadIdRef.current = null;
    nextOlderPageRef.current = 0;
    setHasMore(false);
    setThreadId(null);
    clearMessages();
    setTab("chat");
  }, [setThreadId, clearMessages, setTab]);

  // 「为我设计健身计划」弹窗确认：新开线程 + 标记 plan_design 触发计划设计专用模型全流程
  const handleDesignPlanConfirm = useCallback(() => {
    setDesignPlanOpen(false);
    handleNewChat();
    sendMessage("请帮我设计健身计划", undefined, true);
  }, [sendMessage, handleNewChat]);

  // 当前线程是否为计划设计会话（全程使用计划设计专用模型），供 header 徽标展示
  const isPlanDesignThread = useMemo(
    () => threads.some((t) => t.id === currentThreadId && t.agentMode === "plan_design"),
    [threads, currentThreadId]
  );

  // 计划设计待办队列：从全线程 messages.steps 取最新一次
  // present_plan_queue_tool（入参 {title, todos}）或 update_plan_queue_item_tool
  // （入参.queue = {title, todos}）的快照，驱动顶部持久化进度面板。
  // 面板只渲染待办标题+状态；表单与当日方案在对话内渲染。
  const latestQueue = useMemo<PlanQueue | null>(() => {
    let latest: PlanQueue | null = null;
    for (const msg of messages) {
      for (const s of msg.steps || []) {
        if (s.type !== "tool") continue;
        if (s.tool === "present_plan_queue_tool") {
          const q = (s.input || {}) as PlanQueue;
          if (q && q.todos) latest = q;
        } else if (s.tool === "update_plan_queue_item_tool") {
          const q = (s.input || {}).queue as PlanQueue | undefined;
          if (q && q.todos) latest = q;
        }
      }
    }
    return latest;
  }, [messages]);

  // 队列是否已结束：无任何 pending/in_progress 项（全部完成/跳过）时隐藏面板，
  // 即计划设计流程收尾后面板自动关闭；新一轮设计重新创建队列时会再次出现。
  const queueDone = useMemo(() => {
    if (!latestQueue) return false;
    return !latestQueue.todos.some(
      (t) => t.status === "pending" || t.status === "in_progress"
    );
  }, [latestQueue]);

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
    loadedThreadIdRef.current = id;
    nextOlderPageRef.current = 0;
    setHasMore(false);
    try {
      // 首页请求顺带拿 total；消息数不超过一页时它就是完整消息列表
      const res = await fetch(
        `${API_URL}/chat/threads/${id}/messages?page=1&size=${HISTORY_PAGE_SIZE}`,
        { credentials: "include" }
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
          `${API_URL}/chat/threads/${id}/messages?page=${lastPage}&size=${HISTORY_PAGE_SIZE}`,
          { credentials: "include" }
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
        `${API_URL}/chat/threads/${id}/messages?page=${page}&size=${HISTORY_PAGE_SIZE}`,
        { credentials: "include" }
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

  // 初始消息加载后触发 Conversation 重挂载，让 StickToBottom 正确测量高度（仅首次从 0 变有消息时触发）
  const initialLoadRef = useRef(false);
  useEffect(() => {
    if (messages.length > 0 && !initialLoadRef.current) {
      initialLoadRef.current = true;
      const timer = setTimeout(() => {
        setConversationKey((k) => k + 1);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [messages.length]);

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
    // 真正切换到新会话时才用该会话上次「上下文大小」重置 usage（seedUsage 内部有切换守卫）
    seedUsageForThread(id);
  };

  return (
    <AppLayout>
      <div className="relative flex h-full flex-col">
        {/* 页面顶部 header：AI 教练标题 + 新对话按钮（置于最上方） */}
        <header className="flex shrink-0 items-center justify-between gap-2 border-b border-emerald-100 bg-white/70 px-3 py-2 backdrop-blur sm:px-4 sm:py-2.5">
          <div className="flex min-w-0 items-center gap-2.5">
            <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 shadow-sm shadow-emerald-500/20">
              <BotMessageSquareIcon className="size-4 text-white" />
            </div>
            <div className="min-w-0 leading-tight">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-base font-bold text-emerald-950">AI 教练</h1>
                {isPlanDesignThread && (
                  <span className="hidden shrink-0 items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 sm:inline-flex">
                    <DumbbellIcon className="size-2.5" />
                    计划设计
                  </span>
                )}
              </div>
              <p className="hidden text-xs text-emerald-600/60 sm:block">
                你的私人健身顾问
              </p>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            <Context
              usedTokens={usage.total_tokens}
              maxTokens={MAX_CONTEXT_TOKENS}
              compressionCount={compressionCount}
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
              <span className="hidden sm:inline">新对话</span>
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
        <Conversation key={conversationKey} className="flex-1">
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
                  {["看看我订阅的知识库", "今天练什么好？", "查看我的最近饮食情况", "查看我最近的训练数据"].map(
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
              <MessageItem
                key={msg.id}
                message={msg}
                pendingApproval={pendingApproval}
                onResume={resume}
                isLastAssistant={msg.id === lastAssistantId}
                onSubmitForm={sendMessage}
              />
            ))}
            <div ref={bottomRef} />
          </ConversationContent>
        </Conversation>

        {latestQueue && !queueDone && (
          <PlanQueuePanel queue={latestQueue} onAction={sendMessage} />
        )}

        <div className="border-t border-emerald-100 bg-white/70 p-2.5 backdrop-blur-sm">
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
              <ChatPromptInner
                isStreaming={isStreaming}
                onStop={stop}
                onDesignPlan={() => setDesignPlanOpen(true)}
                kbEnabled={kbEnabled}
                onToggleKb={handleToggleKb}
              />
            </PromptInput>
          </PromptInputProvider>
        </div>

        <DesignPlanDialog
          open={designPlanOpen}
          onOpenChange={setDesignPlanOpen}
          onConfirm={handleDesignPlanConfirm}
        />

        {/* 右侧会话历史抽屉 */}
        {sidebarOpen && (
          <div className="absolute inset-y-0 right-0 z-20 flex w-[85vw] max-w-80 flex-col border-l border-emerald-100 bg-white/95 shadow-xl backdrop-blur">
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
