/**
 * 知识库 MCP 配置面板
 *
 * 展示后端 fastapi-mcp 挂载的管理 MCP 端点：
 * - /mcp/admin 全权限（管理端，认证: 管理员 JWT）
 *
 * 用户 MCP 接入请使用个人中心的用户 API Key（/mcp/user）。
 */
import { useCallback, useState } from "react";
import {
  CheckIcon,
  CopyIcon,
  ServerIcon,
  ShieldCheckIcon,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
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
];

const ADMIN_EXTRA_OPERATIONS: string[] = [
  "create_knowledge_base",
  "update_knowledge_base",
  "delete_knowledge_base",
  "create_document",
  "update_document_content",
  "update_document_metadata",
  "delete_document",
  "reindex_knowledge_base",
  "rebuild_graph",
  "lint_knowledge_base",
  "rebuild_lint",
  "list_subscribers",
  "remove_subscriber",
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

export function KbMcpPanel() {
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === "admin";

  const [baseUrl, setBaseUrl] = useState(
    typeof window !== "undefined" ? window.location.origin : ""
  );

  const trimmedBase = baseUrl.replace(/\/+$/, "");
  const adminUrl = `${trimmedBase}/mcp/admin`;

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
    </div>
  );
}
