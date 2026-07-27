/**
 * 知识库 API 客户端
 *
 * 基于统一 api 封装，按权限分两组：
 * - 用户：读 + 自助订阅
 * - 管理员：写（CRUD / 文档 / 索引 / 订阅者 / 令牌）
 */
import { api } from "@/lib/api";

// ============ 类型 ============

export interface KBListItem {
  id: string;
  name: string;
  description: string;
  slug: string;
  owner_id: string;
  visibility: string;
  subscribed: boolean;
  created_at: string;
}

export interface KB {
  id: string;
  name: string;
  description: string;
  slug: string;
  owner_id: string;
  visibility: string;
  public_slug?: string | null;
  share_token?: string | null;
  schema_config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface KBDocument {
  id: string;
  kb_id: string;
  title: string;
  filename: string;
  path: string;
  source_kind: string;
  file_type: string;
  content_hash?: string | null;
  status: string;
  document_number?: number | null;
  sort_order: number;
  archived: boolean;
  page_count?: number | null;
  last_indexed_at?: string | null;
  stale_since?: string | null;
  tags: string[];
  entity_type?: string | null;
  metadata: Record<string, unknown>;
  version: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface KBDocumentContent {
  id: string;
  title: string;
  filename: string;
  path: string;
  content: string;
  content_hash?: string | null;
  version: number;
  updated_at: string;
}

export interface KBSearchResult {
  chunk_id: string;
  document_id: string;
  document_title: string;
  filename: string;
  path: string;
  chunk_index: number;
  content: string;
  header_breadcrumb?: string | null;
  token_count: number;
  rank: number;
}

export interface KBGraphNode {
  id: string;
  title: string;
  path: string;
  file_type: string;
  source_kind: string;
  tags: string[];
}

export interface KBGraphEdge {
  source: string;
  target: string;
  type: string;
  page?: number | null;
}

export interface KBGraphData {
  nodes: KBGraphNode[];
  edges: KBGraphEdge[];
  stats: Record<string, unknown>;
}

export interface KBSubscription {
  id: string;
  kb_id: string;
  user_id: string;
  user_name?: string | null;
  user_phone?: string | null;
  subscribed_at: string;
}

export interface KBToken {
  id: string;
  kb_id: string;
  token_prefix: string;
  name: string;
  scope: string;
  last_used_at?: string | null;
  expires_at?: string | null;
  revoked_at?: string | null;
  created_at: string;
}

export interface KBTokenCreated {
  token: string;
  token_out: KBToken;
}

export interface KBCreateInput {
  name: string;
  description?: string;
  schema_config?: Record<string, unknown>;
}

export interface KBUpdateInput {
  name?: string;
  description?: string;
  schema_config?: Record<string, unknown>;
}

export interface KBVisibilityInput {
  visibility: "private" | "shared" | "public";
  public_slug?: string | null;
}

export interface KBDocumentCreateInput {
  title: string;
  filename: string;
  path?: string;
  source_kind?: "raw" | "wiki";
  file_type?: string;
  content?: string;
  tags?: string[];
  entity_type?: string | null;
  metadata?: Record<string, unknown>;
}

export interface KBDocumentContentUpdateInput {
  content: string;
  tags?: string[] | null;
  title?: string | null;
  version: number;
}

export interface KBDocumentMetaUpdateInput {
  title?: string;
  tags?: string[];
  entity_type?: string | null;
  metadata?: Record<string, unknown>;
  sort_order?: number;
}

export interface KBTokenCreateInput {
  name: string;
  scope?: "read" | "write";
  expires_at?: string | null;
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

export const kbApi = {
  // ---------- 用户：读 + 订阅 ----------
  list: () => api.get<KBListItem[]>("/knowledge-bases"),
  mySubscriptions: () =>
    api.get<KBListItem[]>("/knowledge-bases/subscriptions"),
  get: (id: string) => api.get<KB>(`/knowledge-bases/${id}`),
  listDocuments: (
    id: string,
    params?: { source_kind?: "raw" | "wiki"; entity_type?: string; include_archived?: boolean }
  ) => api.get<KBDocument[]>(withQuery(`/knowledge-bases/${id}/documents`, params ?? {})),
  getDocument: (kbId: string, docId: string) =>
    api.get<KBDocument>(`/knowledge-bases/${kbId}/documents/${docId}`),
  readDocument: (kbId: string, docId: string) =>
    api.get<KBDocumentContent>(`/knowledge-bases/${kbId}/documents/${docId}/content`),
  search: (kbId: string, query: string, limit = 20) =>
    api.get<KBSearchResult[]>(
      withQuery(`/knowledge-bases/${kbId}/search`, { query, limit })
    ),
  getGraph: (kbId: string) => api.get<KBGraphData>(`/knowledge-bases/${kbId}/graph`),
  getReferences: (kbId: string, docId: string) =>
    api.get<unknown>(`/knowledge-bases/${kbId}/documents/${docId}/references`),
  subscribe: (id: string) => api.post<KBSubscription>(`/knowledge-bases/${id}/subscribe`),
  unsubscribe: (id: string) => api.delete(`/knowledge-bases/${id}/subscribe`),

  // ---------- 管理员：写 ----------
  create: (data: KBCreateInput) => api.post<KB>("/knowledge-bases", data),
  update: (id: string, data: KBUpdateInput) => api.put<KB>(`/knowledge-bases/${id}`, data),
  remove: (id: string) => api.delete<null>(`/knowledge-bases/${id}`),
  setVisibility: (id: string, data: KBVisibilityInput) =>
    api.post<KB>(`/knowledge-bases/${id}/share`, data),
  createDocument: (kbId: string, data: KBDocumentCreateInput) =>
    api.post<KBDocument>(`/knowledge-bases/${kbId}/documents`, data),
  uploadDocument: (kbId: string, formData: FormData) =>
    api.upload<KBDocument>(`/knowledge-bases/${kbId}/documents/upload`, formData),
  updateDocContent: (kbId: string, docId: string, data: KBDocumentContentUpdateInput) =>
    api.put<KBDocument>(`/knowledge-bases/${kbId}/documents/${docId}/content`, data),
  updateDocMeta: (kbId: string, docId: string, data: KBDocumentMetaUpdateInput) =>
    api.patch<KBDocument>(`/knowledge-bases/${kbId}/documents/${docId}`, data),
  deleteDocument: (kbId: string, docId: string) =>
    api.delete<null>(`/knowledge-bases/${kbId}/documents/${docId}`),
  reindex: (kbId: string) =>
    api.post<{ kb_id: string; documents_processed: number; chunks_created: number; references: Record<string, unknown> }>(
      `/knowledge-bases/${kbId}/reindex`
    ),
  rebuildGraph: (kbId: string) =>
    api.post<Record<string, unknown>>(`/knowledge-bases/${kbId}/rebuild-graph`),
  lint: (kbId: string) =>
    api.get<Record<string, unknown>>(`/knowledge-bases/${kbId}/lint`),
  listSubscribers: (kbId: string) =>
    api.get<KBSubscription[]>(`/knowledge-bases/${kbId}/subscribers`),
  removeSubscriber: (kbId: string, userId: string) =>
    api.delete<null>(`/knowledge-bases/${kbId}/subscribers/${userId}`),
  createToken: (kbId: string, data: KBTokenCreateInput) =>
    api.post<KBTokenCreated>(`/knowledge-bases/${kbId}/tokens`, data),
  listTokens: (kbId: string) => api.get<KBToken[]>(`/knowledge-bases/${kbId}/tokens`),
  revokeToken: (kbId: string, tokenId: string) =>
    api.delete<null>(`/knowledge-bases/${kbId}/tokens/${tokenId}`),
};
