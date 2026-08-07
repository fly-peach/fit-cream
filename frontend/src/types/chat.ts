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
  | "step"
  | "approval_needed"
  | "usage"
  | "done"
  | "stopped"
  | "error";

/** Token 使用量 */
export interface TokenUsage {
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

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
  /** 该工具调用开始时的 thinking 文本长度，用于在思考流中内联渲染工具块 */
  thinkingOffset?: number;
}

/** ReAct 步骤类型（步骤流中的节点类型） */
export type AgentStepType = "thought" | "tool" | "reply";

/** ReAct 步骤：思考段或工具调用，按 agent loop 轮次顺序交错 */
export interface AgentStep {
  type: AgentStepType;
  /** tool 步骤的后端 run_id */
  id?: string;
  /** thought 步骤文本 */
  content?: string;
  /** tool 步骤的工具名 */
  tool?: string;
  input?: Record<string, unknown>;
  output?: unknown;
  status?: ToolCallStatus;
  /** 实时增量事件里携带的文本（thought 增量 / tool result 数据） */
  delta?: string;
}

/** HITL 审批状态（对齐 AI SDK ToolUIPart["state"]） */
export type ApprovalState =
  | "approval-requested"
  | "approval-responded"
  | "output-available"
  | "output-denied";

/** 单个待审批的工具操作（HITL） */
export interface ToolApproval {
  /** 中断 id（后端 Interrupt.id） */
  id: string;
  /** 工具名，如 create_plan_tool */
  tool: string;
  /** 工具入参 */
  input: Record<string, unknown>;
  /** 审批请求描述 */
  description?: string;
  /** 允许的决策类型 */
  allowedDecisions: string[];
  /** 审批状态 */
  state: ApprovalState;
  /** 是否批准（state 进入 responded/output 后填充） */
  approved?: boolean;
  /** 用户决策类型 */
  decision?: "approve" | "reject";
}

/** 聊天消息 */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  /** 图片列表（URL 或 base64 data URL），仅用户消息可能携带 */
  images?: string[];
  thinking?: string;
  toolCalls?: ToolCall[];
  /** ReAct 步骤流（新格式优先；历史消息缺失时回退 thinking/toolCalls 旧格式） */
  steps?: AgentStep[];
  /** HITL 审批请求列表（present_plan_tool 提案 + create_plan_tool 中断） */
  approvals?: ToolApproval[];
  createdAt: number;
  isStreaming?: boolean;
}

/** 对话线程 */
export interface Thread {
  id: string;
  /** 用户自定义标题（null 表示未自定义，展示时回退到 lastMessage） */
  title: string | null;
  /** 最后一条助手消息预览（无自定义标题时作为展示与编辑初始值） */
  lastMessage: string | null;
  /** ISO 时间字符串，会话创建时间（首条消息时间） */
  createdAt: string;
  /** ISO 时间字符串，会话最后更新时间 */
  updatedAt: string;
  messageCount: number;
  totalTokens: number;
  /** 线程绑定的 agent 模式（plan_design -> 计划设计专用模型），供徽标展示 */
  agentMode?: string;
}

/** 发送消息请求 */
export interface SendMessageRequest {
  message: string;
  thread_id: string | null;
  images?: string[];
  /** 为 true 时后端新开线程并标记 plan_design，全程路由到计划设计专用模型 */
  plan_design?: boolean;
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

// ===== 计划设计待办队列（present_plan_queue_tool / update_plan_queue_item_tool 入参）=====

export type TrainingType =
  | "fat_loss"
  | "muscle_gain"
  | "recomp"
  | "cardio_only"
  | "maintain";

export type DayType = "strength" | "cardio" | "mixed" | "rest";

export type QueueItemStatus = "pending" | "in_progress" | "completed" | "skipped";

export interface DayExerciseDesign {
  exercise_id?: string;
  custom_name?: string;
  exercise_type: "strength" | "cardio";
  name: string;
  sets?: number;
  reps?: number;
  weight_kg?: number;
  duration_min?: number;
  distance_km?: number;
  rest_seconds?: number;
  notes?: string;
}

export interface DayDesign {
  day_of_week: number;
  focus: string;
  day_type: DayType;
  exercises: DayExerciseDesign[];
  rationale?: string;
}

export interface PlanQueueTodo {
  id: string;
  title: string;
  description?: string;
  status: QueueItemStatus;
  day_type: DayType;
  day_design?: DayDesign;
}

export interface PlanQueuePhase {
  phase_id: string;
  phase_title: string;
  weeks?: number;
  todos: PlanQueueTodo[];
}

export interface PlanQueue {
  goal: string;
  training_type: TrainingType;
  weekly_frequency: number;
  difficulty: string;
  phases: PlanQueuePhase[];
}