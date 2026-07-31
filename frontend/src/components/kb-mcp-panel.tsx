/**
 * 知识库 MCP 配置面板
 *
 * 展示后端 fastapi-mcp 挂载的管理 MCP 端点：
 * - /mcp/admin 全权限（管理端，认证: 管理员 JWT）
 *
 * 并提供该知识库的 API Token 管理（创建 / 列表 / 撤销）。
 * 注意：KB Token 仅作管理员功能保留，不再用于 MCP 接入。
 * 用户 MCP 接入请使用个人中心的用户 API Key（/mcp/user）。
 */
import { useCallback, useEffect, useState } from "react";
import {
  CheckIcon,
  CopyIcon,
  KeyIcon,
  Loader2,
  PlusIcon,
  ServerIcon,
  ShieldCheckIcon,
  Trash2Icon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import { kbApi, type KBToken, type KBTokenCreated } from "@/lib/kb-api";
import { useAuthStore } from "@/stores/auth-store";

const KB_USER_OPERATIONS: string[] = [
  "list_knowledge_bases",
  "list_my_subscriptions",
  "get_knowledge_base",
  "list_documents",
  "get_document",
  "read_document",
  "search_documents",
  "get_graph",
  "get_document_references",
  "subscribe_kb",
  "unsubscribe_kb",
  "get_shared_kb",
  "get_public_kb",
];

const ADMIN_EXTRA_OPERATIONS: string[] = [
  "create_knowledge_base",
  "update_knowledge_base",
  "delete_knowledge_base",
  "set_kb_visibility",
  "create_document",
  "upload_document",
  "update_document_content",
  "update_document_metadata",
  "delete_document",
  "reindex_knowledge_base",
  "rebuild_graph",
  "lint_knowledge_base",
  "list_subscribers",
  "remove_subscriber",
  "create_kb_token",
  "list_kb_tokens",
  "revoke_kb_token",
];

function CopyButton({
  text,
  fieldKey,
  className,
}: {
  text: string;
  fieldKey: string;
  className?: string;
}) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // 剪贴板被拒绝时静默失败
    }
  }, [text]);
  return (
    <Button
      type="button"
      variant="ghost"
      size="icon-sm"
      className={cn("shrink-0 text-emerald-600 hover:bg-emerald-50", className)}
      onClick={handleCopy}
      title="复制"
    >
      {copied ? (
        <CheckIcon className="size-3.5 text-emerald-500" />
      ) : (
        <CopyIcon className="size-3.5" />
      )}
      <span className="sr-only">复制 {fieldKey}</span>
    </Button>
  );
}

function EndpointRow({
  icon,
  label,
  url,
  authHint,
  opsCount,
  accent,
}: {
  icon: React.ReactNode;
  label: string;
  url: string;
  authHint: string;
  opsCount: number;
  accent: string;
}) {
  return (
    <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3">
      <div className="mb-1.5 flex items-center gap-2">
        <span className={cn("flex size-6 items-center justify-center rounded-md", accent)}>
          {icon}
        </span>
        <span className="text-sm font-semibold text-emerald-900">{label}</span>
        <Badge
          variant="outline"
          className="ml-auto border-emerald-200 text-[10px] text-emerald-600"
        >
          {opsCount} operations
        </Badge>
      </div>
      <div className="flex items-center gap-1.5">
        <code className="min-w-0 flex-1 truncate rounded bg-white/80 px-2 py-1.5 font-mono text-xs text-emerald-800">
          {url}
        </code>
        <CopyButton text={url} fieldKey={label} />
      </div>
      <p className="mt-1.5 text-[11px] text-emerald-600/70">{authHint}</p>
    </div>
  );
}

export function KbMcpPanel({ kbId }: { kbId: string }) {
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === "admin";

  const [baseUrl, setBaseUrl] = useState(
    typeof window !== "undefined" ? window.location.origin : ""
  );
  const [tokens, setTokens] = useState<KBToken[]>([]);
  const [loading, setLoading] = useState(isAdmin);
  const [creating, setCreating] = useState(false);
  const [newTokenName, setNewTokenName] = useState("");
  const [createdToken, setCreatedToken] = useState<KBTokenCreated | null>(null);
  const [error, setError] = useState("");

  const trimmedBase = baseUrl.replace(/\/+$/, "");
  const adminUrl = `${trimmedBase}/mcp/admin`;

  const loadTokens = useCallback(async () => {
    if (!isAdmin) return;
    try {
      setTokens(await kbApi.listTokens(kbId));
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载令牌失败");
    } finally {
      setLoading(false);
    }
  }, [kbId, isAdmin]);

  useEffect(() => {
    loadTokens();
  }, [loadTokens]);

  const handleCreate = async () => {
    const name = newTokenName.trim() || `token-${new Date().toISOString().slice(0, 10)}`;
    setCreating(true);
    setError("");
    try {
      const t = await kbApi.createToken(kbId, { name, scope: "read" });
      setCreatedToken(t);
      setNewTokenName("");
      await loadTokens();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "创建令牌失败");
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (tokenId: string) => {
    setError("");
    try {
      await kbApi.revokeToken(kbId, tokenId);
      await loadTokens();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "撤销令牌失败");
    }
  };

  return (
    <div className="space-y-4">
      <Card className="border-emerald-100 bg-white/80">
        <CardContent className="space-y-3 p-5">
          <div className="flex items-center gap-2">
            <ServerIcon className="size-4 text-emerald-600" />
            <h3 className="text-sm font-semibold text-emerald-950">MCP 端点</h3>
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-emerald-700">
              后端地址（Base URL）
            </label>
            <Input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://your-host"
              className="rounded-xl border-emerald-200 bg-white/70 font-mono text-xs"
            />
            <p className="mt-1 text-[11px] text-emerald-600/60">
              生产环境前后端同源时默认即可；本地开发若前后端分离，请改为后端地址（如
              <code className="mx-1 rounded bg-emerald-50 px-1">http://localhost:8000</code>）。
            </p>
          </div>

          {isAdmin && (
            <EndpointRow
              icon={<ShieldCheckIcon className="size-3.5 text-white" />}
              label="管理 MCP（/mcp/admin）"
              url={adminUrl}
              authHint="认证：管理员 JWT（Bearer）。仅管理员可用，含全部读写操作。"
              opsCount={KB_USER_OPERATIONS.length + ADMIN_EXTRA_OPERATIONS.length}
              accent="bg-rose-500"
            />
          )}

          <p className="rounded-lg border border-emerald-100 bg-emerald-50/40 px-3 py-2 text-[11px] text-emerald-600/70">
            用户 MCP 接入（健身数据 + 知识库只读）请使用个人中心的用户 API Key，端点为
            <code className="mx-1 rounded bg-emerald-50 px-1">{trimmedBase}/mcp/user</code>。
          </p>

          {isAdmin && (
            <details className="rounded-lg border border-emerald-100 bg-emerald-50/40 p-3 text-xs text-emerald-700">
              <summary className="cursor-pointer font-medium">
                管理 MCP 可用操作（{KB_USER_OPERATIONS.length + ADMIN_EXTRA_OPERATIONS.length} 个）
              </summary>
              <div className="mt-2 space-y-1.5">
                <p className="font-medium text-emerald-800">
                  知识库用户态（{KB_USER_OPERATIONS.length}）：
                </p>
                <code className="block break-all text-[11px] text-emerald-700/80">
                  {KB_USER_OPERATIONS.join(", ")}
                </code>
                <p className="mt-2 font-medium text-emerald-800">
                  管理额外（{ADMIN_EXTRA_OPERATIONS.length}）：
                </p>
                <code className="block break-all text-[11px] text-emerald-700/80">
                  {ADMIN_EXTRA_OPERATIONS.join(", ")}
                </code>
              </div>
            </details>
          )}
        </CardContent>
      </Card>

      {isAdmin ? (
        <Card className="border-emerald-100 bg-white/80">
          <CardContent className="space-y-3 p-5">
            <div className="flex items-center gap-2">
              <KeyIcon className="size-4 text-emerald-600" />
              <h3 className="text-sm font-semibold text-emerald-950">API Token</h3>
              <span className="text-xs text-emerald-600/60">
                知识库管理功能（不用于 MCP 接入）
              </span>
            </div>

            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
                {error}
              </div>
            )}

            {createdToken && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                <p className="mb-1 text-xs font-semibold text-amber-800">
                  令牌已创建，请立即保存（仅显示一次）：
                </p>
                <div className="flex items-center gap-1.5">
                  <code className="min-w-0 flex-1 truncate rounded bg-white/80 px-2 py-1.5 font-mono text-xs text-amber-900">
                    {createdToken.token}
                  </code>
                  <CopyButton text={createdToken.token} fieldKey="新建令牌" />
                </div>
                <p className="mt-1.5 text-[11px] text-amber-700">
                  名称：{createdToken.token_out.name} · 权限：{createdToken.token_out.scope}
                </p>
              </div>
            )}

            <div className="flex items-center gap-2">
              <Input
                value={newTokenName}
                onChange={(e) => setNewTokenName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleCreate();
                }}
                placeholder="令牌名称（如：我的 Agent）"
                className="rounded-xl border-emerald-200 bg-white/70 text-sm"
              />
              <Button
                onClick={handleCreate}
                disabled={creating}
                size="sm"
                className="shrink-0 gap-1.5 bg-emerald-600 text-white hover:bg-emerald-500"
              >
                {creating ? (
                  <Loader2 className="size-3.5 animate-spin" />
                ) : (
                  <PlusIcon className="size-3.5" />
                )}
                创建
              </Button>
            </div>

            {loading ? (
              <div className="flex items-center justify-center py-6 text-emerald-500">
                <Loader2 className="size-5 animate-spin" />
              </div>
            ) : tokens.length === 0 ? (
              <p className="py-6 text-center text-xs text-emerald-600/50">
                暂无令牌
              </p>
            ) : (
              <ul className="space-y-1.5">
                {tokens.map((t) => {
                  const revoked = !!t.revoked_at;
                  const expired = !!t.expires_at && new Date(t.expires_at) < new Date();
                  return (
                    <li
                      key={t.id}
                      className="flex items-center gap-2 rounded-lg border border-emerald-100 bg-emerald-50/40 px-3 py-2"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium text-emerald-900">
                            {t.name}
                          </span>
                          <Badge
                            variant="outline"
                            className="shrink-0 border-emerald-200 text-[10px] text-emerald-600"
                          >
                            {t.scope}
                          </Badge>
                          {revoked && (
                            <Badge className="bg-red-100 text-[10px] text-red-600">已撤销</Badge>
                          )}
                          {!revoked && expired && (
                            <Badge className="bg-amber-100 text-[10px] text-amber-700">已过期</Badge>
                          )}
                        </div>
                        <p className="truncate font-mono text-[11px] text-emerald-500/70">
                          {t.token_prefix}… · 创建于 {new Date(t.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      {!revoked && (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          className="shrink-0 text-emerald-400 hover:bg-red-50 hover:text-red-600"
                          onClick={() => handleRevoke(t.id)}
                          title="撤销"
                        >
                          <Trash2Icon className="size-3.5" />
                        </Button>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      ) : (
        <Card className="border-emerald-100 bg-white/80">
          <CardContent className="space-y-2 p-5">
            <div className="flex items-center gap-2">
              <KeyIcon className="size-4 text-emerald-600" />
              <h3 className="text-sm font-semibold text-emerald-950">API Token</h3>
            </div>
            <p className="text-xs text-emerald-700/70">
              仅管理员可创建与管理 API Token。
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
