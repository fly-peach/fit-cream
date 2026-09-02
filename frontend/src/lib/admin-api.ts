/**
 * 管理后台 API 客户端
 *
 * 基于统一 api 封装，全部端点要求 admin 权限（后端 get_admin_user 校验）。
 */
import { api } from "@/lib/api";

// ============ 类型 ============

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface AdminUserListItem {
  id: string;
  phone: string | null;
  name: string | null;
  gender: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  last_login_at: string | null;
  last_login_ip: string | null;
  created_at: string;
  plan_count: number;
  checkin_count: number;
  total_tokens: number;
  tokens_7d: number;
}

export interface AdminUserHealthMetric {
  measure_date: string | null;
  weight_kg: number | null;
  body_fat_pct: number | null;
  bmi: number | null;
}

export interface AdminUserSettings {
  goal: string | null;
  weekly_training_goal: number | null;
  calorie_goal: number | null;
  target_weight_kg: number | null;
}

export interface AdminUserDetail extends AdminUserListItem {
  diet_plan_count: number;
  settings: AdminUserSettings | null;
  latest_health_metric: AdminUserHealthMetric | null;
}

export interface AdminUserUpdateInput {
  is_active?: boolean;
  role?: "user" | "admin";
}

export interface AdminCheckin {
  id: string;
  date: string;
  duration_min: number | null;
  actual_intensity: string | null;
  calories_burned: number | null;
  mood: number | null;
  note: string | null;
  created_at: string;
}

export interface AdminUsersStats {
  total: number;
  new_7d: number;
  active_7d: number;
}

export interface AdminTrainingStats {
  total_checkins: number;
  checkins_30d: number;
  total_plans: number;
  active_plans: number;
}

export interface AdminKbStats {
  total_kbs: number;
  total_documents: number;
  pending_documents: number;
  total_chunks: number;
}

export interface AdminConversationStats {
  total_threads: number;
  total_messages: number;
  threads_7d: number;
}

export interface AdminTokenStats {
  total_tokens: number;
  tokens_7d: number;
}

export interface AdminOverviewStats {
  users: AdminUsersStats;
  training: AdminTrainingStats;
  kb: AdminKbStats;
  conversation: AdminConversationStats;
  tokens: AdminTokenStats;
}

export interface AdminTrends {
  days: string[];
  registrations: number[];
  checkins: number[];
  conversations: number[];
  active_users: number[];
  tokens: number[];
}

export interface AdminKbListItem {
  id: string;
  name: string;
  slug: string;
  description: string;
  owner_name: string | null;
  document_count: number;
  chunk_count: number;
  pending_document_count: number;
  created_at: string;
  updated_at: string;
}

export interface TokenSourceStat {
  source: string;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  llm_calls: number;
}

export interface TokenDailyPoint {
  usage_date: string;
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
}

export interface UserTokenUsageOut {
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  llm_calls: number;
  by_source: TokenSourceStat[];
  daily: TokenDailyPoint[];
}

export interface AdminListUsersParams {
  page?: number;
  size?: number;
  keyword?: string;
  role?: "user" | "admin";
  is_active?: boolean;
}

// ============ 计费（余额 / 充值申请 / 单价） ============

export interface BillingAccount {
  balance: number;
  total_recharged: number;
  total_granted: number;
  total_consumed: number;
  status: string;
}

export interface BillingPricing {
  model: string;
  input_price: number;
  output_price: number;
  cache_read_price: number;
  cost_input_price: number;
  cost_output_price: number;
  cost_cache_read_price: number;
  embedding_price: number;
  rerank_price: number;
}

export interface RechargeApplication {
  id: string;
  app_no: string;
  amount: number;
  method: string;
  note: string | null;
  status: "pending" | "confirmed" | "rejected";
  review_note: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface BillingOverview {
  recharged: string;
  granted: string;
  consumed: string;
  estimated_cost: string;
  pending_applications: number;
  pricing: {
    input_price: string;
    output_price: string;
    cache_read_price: string;
  };
}

export interface AdminListApplicationsParams {
  status?: "pending" | "confirmed" | "rejected";
  page?: number;
  size?: number;
}

export interface AdminListKbsParams {
  page?: number;
  size?: number;
  keyword?: string;
}

// ============ 检索质量（动作库搜索评估 / embedding 回填） ============

/** 单模式聚合指标（filter 派生给 precision/hit_rate，手挑给 recall/mrr） */
export interface SearchQualityModeAgg {
  queries: number;
  average_precision_at_k?: number | null;
  average_hit_rate_at_10?: number | null;
  average_recall_at_k?: number | null;
  average_mrr_at_k?: number | null;
}

export interface SearchQualityAggregates {
  filter_derived: {
    queries: number;
    by_mode: Record<string, SearchQualityModeAgg | null>;
  };
  hand_picked: {
    queries: number;
    by_mode: Record<string, SearchQualityModeAgg | null>;
  };
}

/** 单条黄金查询明细（per_mode 按 kind 给不同指标；hit_counts 为各模式命中数） */
export interface SearchQualityDetail {
  query: string;
  kind: "filter_derived" | "hand_picked";
  relevant_count: number;
  relevant_filter: Record<string, unknown> | null;
  keyword_terms: string[] | null;
  per_mode: Record<string, Record<string, number | null> | null>;
  hit_counts: Record<string, number | null>;
  vector_rerank_top10: string[] | null;
}

export interface SearchQualityEval {
  schema_version: number;
  k: number;
  total_queries: number;
  zero_hit_queries: { query: string; kind: string }[];
  aggregates: SearchQualityAggregates;
  details: SearchQualityDetail[];
}

export interface BackfillResult {
  ok?: number;
  failed?: number;
  total?: number;
  message: string;
}

export interface BackfillStatus {
  running: boolean;
  started_at: number | null;
  finished_at: number | null;
  result: BackfillResult | null;
}

function withQuery(path: string, params: Record<string, unknown>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") sp.append(k, String(v));
  }
  const qs = sp.toString();
  return qs ? `${path}?${qs}` : path;
}

// ============ 客户端 ============

export const adminApi = {
  // ---------- 用户管理 ----------
  listUsers: (params: AdminListUsersParams = {}) =>
    api.get<Paginated<AdminUserListItem>>(
      withQuery("/admin/users", params as Record<string, unknown>)
    ),
  getUser: (userId: string) => api.get<AdminUserDetail>(`/admin/users/${userId}`),
  listUserCheckins: (userId: string, limit = 20) =>
    api.get<AdminCheckin[]>(`/admin/users/${userId}/checkins?limit=${limit}`),
  getUserTokenUsage: (userId: string, days = 30) =>
    api.get<UserTokenUsageOut>(`/admin/users/${userId}/token-usage?days=${days}`),
  updateUser: (userId: string, data: AdminUserUpdateInput) =>
    api.patch<AdminUserListItem>(`/admin/users/${userId}`, data),

  // ---------- 用户计费 ----------
  getUserBilling: (userId: string) =>
    api.get<BillingAccount>(`/admin/users/${userId}/billing`),
  grantUserBilling: (userId: string, amount: number, reason?: string) =>
    api.post<BillingAccount>(`/admin/users/${userId}/billing/grant`, {
      amount,
      reason,
    }),

  // ---------- 充值申请核销 ----------
  listRechargeApplications: (params: AdminListApplicationsParams = {}) =>
    api.get<Paginated<RechargeApplication>>(
      withQuery("/admin/billing/applications", params as Record<string, unknown>)
    ),
  reviewRechargeApplication: (
    appId: string,
    approve: boolean,
    reviewNote?: string
  ) =>
    api.post<RechargeApplication>(
      `/admin/billing/applications/${appId}/review`,
      { approve, review_note: reviewNote }
    ),

  // ---------- 计费单价与概览 ----------
  getBillingPricing: () => api.get<BillingPricing>("/admin/billing/pricing"),
  updateBillingPricing: (data: BillingPricing) =>
    api.put<BillingPricing>("/admin/billing/pricing", data),
  getBillingOverview: () => api.get<BillingOverview>("/admin/billing/overview"),

  // ---------- 全局统计 ----------
  getOverview: () => api.get<AdminOverviewStats>("/admin/stats/overview"),
  getTrends: (days = 30) =>
    api.get<AdminTrends>(`/admin/stats/trends?days=${days}`),

  // ---------- 知识库统计列表 ----------
  listKbs: (params: AdminListKbsParams = {}) =>
    api.get<Paginated<AdminKbListItem>>(
      withQuery("/admin/knowledge-bases", params as Record<string, unknown>)
    ),

  // ---------- 检索质量（动作库搜索评估 / embedding 回填） ----------
  runSearchQualityEval: (k = 20) =>
    api.post<SearchQualityEval>(`/admin/search-quality/eval?k=${k}`),
  triggerSearchBackfill: (force = false) =>
    api.post<{ started: boolean; running: boolean; message: string }>(
      `/admin/search-quality/backfill?force=${force}`
    ),
  getSearchBackfillStatus: () =>
    api.get<BackfillStatus>("/admin/search-quality/backfill/status"),
};
