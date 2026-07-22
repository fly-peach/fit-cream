/**
 * FitCream 聊天类型定义
 */

/** SSE 事件类型 */
export type SSEEventType =
  | "start"
  | "thinking"
  | "token"
  | "tool_start"
  | "tool_result"
  | "done"
  | "stopped"
  | "error";

/** SSE 事件 */
export interface SSEEvent {
  event: SSEEventType;
  data: Record<string, unknown>;
}

/** 消息角色 */
export type MessageRole = "user" | "assistant";

/** Tool 调用状态 */
export type ToolCallStatus = "running" | "completed" | "error";

/** Tool 调用记录 */
export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
  output?: unknown;
  error?: string;
  status: ToolCallStatus;
}

/** 聊天消息 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  thinking?: string;
  toolCalls?: ToolCall[];
  createdAt: number;
  isStreaming?: boolean;
}

/** 对话线程 */
export interface Thread {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messageCount: number;
}

/** 发送消息请求 */
export interface SendMessageRequest {
  message: string;
  thread_id: string | null;
}

/** 线程列表响应 */
export interface ThreadListResponse {
  threads: Thread[];
}

/** 消息历史响应 */
export interface MessageHistoryResponse {
  messages: ChatMessage[];
  thread_id: string;
}