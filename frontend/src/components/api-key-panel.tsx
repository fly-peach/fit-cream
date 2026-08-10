import { useCallback, useEffect, useState } from "react";
import {
  CheckIcon,
  ChevronDownIcon,
  CopyIcon,
  KeyIcon,
  Loader2,
  PlusIcon,
  RefreshCwIcon,
  Trash2Icon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { ApiError, apiKeyApi, type UserApiKeyCreated, type UserApiKeyOut } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";

function CopyButton({ text, className }: { text: string; className?: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard denied */
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
      {copied ? <CheckIcon className="size-3.5 text-emerald-500" /> : <CopyIcon className="size-3.5" />}
    </Button>
  );
}

export function ApiKeyPanel() {
  const role = useAuthStore((s) => s.user?.role);
  const isAdmin = role === "admin";

  const [open, setOpen] = useState(false);
  const [baseUrl, setBaseUrl] = useState(
    typeof window !== "undefined" ? window.location.origin : ""
  );
  const [keyMeta, setKeyMeta] = useState<UserApiKeyOut | null>(null);
  const [created, setCreated] = useState<UserApiKeyCreated | null>(null);
  const [keyName, setKeyName] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    try {
      setKeyMeta(await apiKeyApi.get());
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleCreate = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await apiKeyApi.create(keyName.trim() || undefined);
      setCreated(result);
      setKeyMeta(result.key_out);
      setKeyName("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "创建失败");
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async () => {
    setBusy(true);
    setError("");
    try {
      await apiKeyApi.delete();
      setKeyMeta(null);
      setCreated(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "删除失败");
    } finally {
      setBusy(false);
    }
  };

  const trimmedBase = baseUrl.replace(/\/+$/, "");
  const mcpUrl = `${trimmedBase}/mcp/${isAdmin ? "admin" : "user"}`;
  const keyForConfig = created?.key ?? "<YOUR_API_KEY>";
  const mcpConfig = JSON.stringify(
    {
      mcpServers: {
        fitcream: {
          url: mcpUrl,
          headers: { Authorization: `Bearer ${keyForConfig}` },
        },
      },
    },
    null,
    2
  );

  return (
    <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
      <Collapsible open={open} onOpenChange={setOpen}>
        <CardContent className="space-y-4 p-5">
          <CollapsibleTrigger className="flex w-full items-center gap-2 text-left">
            <KeyIcon className="size-4 text-emerald-600" />
            <h3 className="flex-1 text-sm font-semibold text-emerald-950">
              API Key（MCP 接入）
            </h3>
            <ChevronDownIcon
              className={cn(
                "size-4 text-emerald-500 transition-transform",
                open && "rotate-180"
              )}
            />
          </CollapsibleTrigger>

          <CollapsibleContent>
            <div className="space-y-4">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
            {error}
          </div>
        )}

        {created && (
          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
            <p className="mb-1 text-xs font-semibold text-amber-800">
              API Key 已生成，请立即保存（仅显示一次）：
            </p>
            <div className="flex items-center gap-1.5">
              <code className="min-w-0 flex-1 truncate rounded bg-white/80 px-2 py-1.5 font-mono text-xs text-amber-900">
                {created.key}
              </code>
              <CopyButton text={created.key} />
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex items-center justify-center py-6 text-emerald-500">
            <Loader2 className="size-5 animate-spin" />
          </div>
        ) : keyMeta ? (
          <div className="space-y-3">
            <div className="rounded-lg border border-emerald-100 bg-emerald-50/40 px-3 py-2 text-xs text-emerald-700">
              <p>
                前缀：<code className="font-mono">{keyMeta.key_prefix}…</code>
                {keyMeta.name && <span className="ml-2">名称：{keyMeta.name}</span>}
              </p>
              <p className="mt-1 text-emerald-600/60">
                创建于 {new Date(keyMeta.created_at).toLocaleDateString()}
                {keyMeta.last_used_at &&
                  ` · 最近使用 ${new Date(keyMeta.last_used_at).toLocaleDateString()}`}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Input
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                placeholder="新名称（可选，重新生成）"
                className="rounded-xl border-emerald-200 bg-white/70 text-sm"
              />
              <Button
                onClick={handleCreate}
                disabled={busy}
                size="sm"
                className="shrink-0 gap-1.5 bg-emerald-600 text-white hover:bg-emerald-500"
              >
                {busy ? <Loader2 className="size-3.5 animate-spin" /> : <RefreshCwIcon className="size-3.5" />}
                重新生成
              </Button>
              <Button
                onClick={handleDelete}
                disabled={busy}
                size="sm"
                variant="ghost"
                className="shrink-0 gap-1.5 text-red-500 hover:bg-red-50 hover:text-red-600"
              >
                <Trash2Icon className="size-3.5" />
                删除
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            <p className="text-xs text-emerald-700/70">
              生成 API Key 后可通过 MCP 客户端（Claude Desktop、Cursor 等）接入你的健身数据与知识库。一人一把，重新生成会替换旧 Key。
              {isAdmin && "管理员账号将接入管理端点，可访问全部知识库并执行管理操作。"}
            </p>
            <div className="flex items-center gap-2">
              <Input
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                placeholder="名称（可选，如：我的 Agent）"
                className="rounded-xl border-emerald-200 bg-white/70 text-sm"
              />
              <Button
                onClick={handleCreate}
                disabled={busy}
                size="sm"
                className="shrink-0 gap-1.5 bg-emerald-600 text-white hover:bg-emerald-500"
              >
                {busy ? <Loader2 className="size-3.5 animate-spin" /> : <PlusIcon className="size-3.5" />}
                生成
              </Button>
            </div>
          </div>
        )}

        <div className="space-y-2">
          <label className="block text-xs font-medium text-emerald-700">后端地址（Base URL）</label>
          <Input
            value={baseUrl}
            onChange={(e) => setBaseUrl(e.target.value)}
            placeholder="https://your-host"
            className="rounded-xl border-emerald-200 bg-white/70 font-mono text-xs"
          />
        </div>

        <div>
          <p className="mb-1.5 text-xs font-medium text-emerald-700">MCP 客户端配置</p>
          <div className="relative">
            <pre className="max-h-56 overflow-auto rounded-xl border border-emerald-100 bg-emerald-950/95 p-3 font-mono text-xs leading-relaxed text-emerald-100">
              {mcpConfig}
            </pre>
            <CopyButton
              text={mcpConfig}
              className="absolute right-2 top-2 bg-white/90 shadow-sm hover:bg-white"
            />
          </div>
          <p className="mt-1.5 text-[11px] text-emerald-600/60">
            端点 <code className="rounded bg-emerald-50 px-1">{mcpUrl}</code> · 认证：Authorization: Bearer &lt;API Key&gt;
            {isAdmin ? "（管理端点，可访问全部知识库）" : "（用户端点，仅可访问已订阅的知识库）"}
          </p>
        </div>
            </div>
          </CollapsibleContent>
        </CardContent>
      </Collapsible>
    </Card>
  );
}
