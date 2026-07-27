import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeftIcon,
  CopyIcon,
  FileTextIcon,
  Loader2,
  PlusIcon,
  RefreshCwIcon,
  TrashIcon,
  UploadIcon,
  KeyIcon,
  UsersIcon,
  ShieldCheckIcon,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import {
  kbApi,
  type KB,
  type KBDocument,
  type KBDocumentContent,
  type KBSubscription,
  type KBToken,
  type KBTokenCreated,
} from "@/lib/kb-api";

export default function AdminKbDetailPage() {
  const { kbId = "" } = useParams();
  const [kb, setKb] = useState<KB | null>(null);
  const [docs, setDocs] = useState<KBDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // 文档创建
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({
    title: "",
    filename: "",
    content: "",
    source_kind: "wiki" as "raw" | "wiki",
  });
  const [creating, setCreating] = useState(false);

  // 文档编辑
  const [editOpen, setEditOpen] = useState(false);
  const [editDoc, setEditDoc] = useState<KBDocument | null>(null);
  const [editContent, setEditContent] = useState<KBDocumentContent | null>(null);
  const [editText, setEditText] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editLoading, setEditLoading] = useState(false);

  // 上传
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  // 索引
  const [reindexResult, setReindexResult] = useState<string>("");
  const [indexBusy, setIndexBusy] = useState(false);

  // Lint
  const [lintReport, setLintReport] = useState<Record<string, unknown> | null>(null);
  const [lintBusy, setLintBusy] = useState(false);

  // 订阅者
  const [subs, setSubs] = useState<KBSubscription[]>([]);
  const [subsLoading, setSubsLoading] = useState(false);

  // 令牌
  const [tokens, setTokens] = useState<KBToken[]>([]);
  const [tokensLoading, setTokensLoading] = useState(false);
  const [tokenOpen, setTokenOpen] = useState(false);
  const [tokenForm, setTokenForm] = useState({
    name: "",
    scope: "read" as "read" | "write",
  });
  const [tokenCreating, setTokenCreating] = useState(false);
  const [createdToken, setCreatedToken] = useState<KBTokenCreated | null>(null);

  const load = useCallback(async () => {
    try {
      const [k, d] = await Promise.all([
        kbApi.get(kbId),
        kbApi.listDocuments(kbId),
      ]);
      setKb(k);
      setDocs(d);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    load();
  }, [load]);

  // ---------- 文档 ----------
  const createDoc = async () => {
    if (!createForm.title.trim() || !createForm.filename.trim()) return;
    setCreating(true);
    try {
      await kbApi.createDocument(kbId, {
        title: createForm.title,
        filename: createForm.filename,
        content: createForm.content,
        source_kind: createForm.source_kind,
      });
      setCreateOpen(false);
      setCreateForm({ title: "", filename: "", content: "", source_kind: "wiki" });
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "创建失败");
    } finally {
      setCreating(false);
    }
  };

  const openEdit = async (doc: KBDocument) => {
    setEditDoc(doc);
    setEditLoading(true);
    setEditOpen(true);
    try {
      const c = await kbApi.readDocument(kbId, doc.id);
      setEditContent(c);
      setEditText(c.content);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载内容失败");
    } finally {
      setEditLoading(false);
    }
  };

  const saveEdit = async () => {
    if (!editDoc || !editContent) return;
    setEditSaving(true);
    try {
      await kbApi.updateDocContent(kbId, editDoc.id, {
        content: editText,
        version: editContent.version,
        title: editDoc.title,
      });
      setEditOpen(false);
      setEditDoc(null);
      setEditContent(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "保存失败（可能版本冲突）");
    } finally {
      setEditSaving(false);
    }
  };

  const deleteDoc = async (doc: KBDocument) => {
    if (!confirm(`删除文档「${doc.title}」？`)) return;
    try {
      await kbApi.deleteDocument(kbId, doc.id);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "删除失败");
    }
  };

  const onUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      await kbApi.uploadDocument(kbId, fd);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "上传失败");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  // ---------- 索引 ----------
  const reindex = async () => {
    setIndexBusy(true);
    try {
      const r = await kbApi.reindex(kbId);
      setReindexResult(
        `已处理 ${r.documents_processed} 个文档，生成 ${r.chunks_created} 个分块`
      );
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "重建索引失败");
    } finally {
      setIndexBusy(false);
    }
  };

  const rebuildGraph = async () => {
    setIndexBusy(true);
    try {
      await kbApi.rebuildGraph(kbId);
      setReindexResult("知识图谱已重建");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "重建图谱失败");
    } finally {
      setIndexBusy(false);
    }
  };

  // ---------- Lint ----------
  const runLint = async () => {
    setLintBusy(true);
    try {
      setLintReport(await kbApi.lint(kbId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Lint 失败");
    } finally {
      setLintBusy(false);
    }
  };

  // ---------- 订阅者 ----------
  const loadSubs = async () => {
    setSubsLoading(true);
    try {
      setSubs(await kbApi.listSubscribers(kbId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载订阅者失败");
    } finally {
      setSubsLoading(false);
    }
  };

  const removeSub = async (userId: string) => {
    if (!confirm("移除该订阅者？")) return;
    try {
      await kbApi.removeSubscriber(kbId, userId);
      setSubs((prev) => prev.filter((s) => s.user_id !== userId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "移除失败");
    }
  };

  // ---------- 令牌 ----------
  const loadTokens = async () => {
    setTokensLoading(true);
    try {
      setTokens(await kbApi.listTokens(kbId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载令牌失败");
    } finally {
      setTokensLoading(false);
    }
  };

  const createToken = async () => {
    if (!tokenForm.name.trim()) return;
    setTokenCreating(true);
    try {
      const created = await kbApi.createToken(kbId, {
        name: tokenForm.name,
        scope: tokenForm.scope,
      });
      setCreatedToken(created);
      setTokenOpen(false);
      setTokenForm({ name: "", scope: "read" });
      await loadTokens();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "创建令牌失败");
    } finally {
      setTokenCreating(false);
    }
  };

  const revokeToken = async (tokenId: string) => {
    if (!confirm("撤销该令牌？")) return;
    try {
      await kbApi.revokeToken(kbId, tokenId);
      setTokens((prev) => prev.filter((t) => t.id !== tokenId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "撤销失败");
    }
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-5xl space-y-6 p-6">
          <div className="flex items-center gap-3">
            <Link
              to="/admin/knowledge-bases"
              className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "size-9")}
            >
              <ArrowLeftIcon className="size-4" />
            </Link>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-bold text-emerald-950">
                {kb?.name ?? "知识库"}
              </h1>
              <p className="text-sm text-emerald-600/60">管理文档、索引、订阅者与令牌</p>
            </div>
          </div>

          {error && (
            <div className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              <span>{error}</span>
              <button onClick={() => setError("")} className="text-red-400">
                ✕
              </button>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : (
            <Tabs defaultValue="docs">
              <TabsList className="bg-emerald-50">
                <TabsTrigger value="docs">文档（{docs.length}）</TabsTrigger>
                <TabsTrigger value="index">索引</TabsTrigger>
                <TabsTrigger value="lint" onClick={runLint}>Lint</TabsTrigger>
                <TabsTrigger value="subs" onClick={loadSubs}>订阅者</TabsTrigger>
                <TabsTrigger value="tokens" onClick={loadTokens}>令牌</TabsTrigger>
              </TabsList>

              {/* 文档管理 */}
              <TabsContent value="docs" className="mt-4 space-y-3">
                <div className="flex gap-2">
                  <Button
                    onClick={() => setCreateOpen(true)}
                    className="bg-emerald-600 text-white hover:bg-emerald-500"
                  >
                    <PlusIcon className="size-4" />
                    新建文档
                  </Button>
                  <input ref={fileRef} type="file" onChange={onUpload} className="hidden" />
                  <Button variant="outline" onClick={() => fileRef.current?.click()} disabled={uploading}>
                    {uploading ? <Loader2 className="size-4 animate-spin" /> : <UploadIcon className="size-4" />}
                    上传文件
                  </Button>
                </div>
                {docs.length === 0 ? (
                  <p className="py-10 text-center text-sm text-emerald-600/50">暂无文档</p>
                ) : (
                  docs.map((d) => (
                    <Card key={d.id} className="border-emerald-100 bg-white/80">
                      <CardContent className="flex items-center gap-3 p-4">
                        <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100">
                          <FileTextIcon className="size-4 text-emerald-600" />
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate font-medium text-emerald-950">{d.title}</p>
                          <p className="truncate text-xs text-emerald-600/60">
                            {d.filename} · {d.file_type.toUpperCase()} · v{d.version}
                            {d.stale_since && " · 已过期"}
                          </p>
                        </div>
                        <Button variant="ghost" size="sm" onClick={() => openEdit(d)}>
                          编辑
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="hover:bg-red-50 hover:text-red-600"
                          onClick={() => deleteDoc(d)}
                        >
                          <TrashIcon className="size-4" />
                        </Button>
                      </CardContent>
                    </Card>
                  ))
                )}
              </TabsContent>

              {/* 索引 */}
              <TabsContent value="index" className="mt-4 space-y-4">
                <div className="flex flex-wrap gap-2">
                  <Button onClick={reindex} disabled={indexBusy} className="bg-emerald-600 text-white hover:bg-emerald-500">
                    {indexBusy ? <Loader2 className="size-4 animate-spin" /> : <RefreshCwIcon className="size-4" />}
                    重建索引
                  </Button>
                  <Button onClick={rebuildGraph} disabled={indexBusy} variant="outline">
                    重建知识图谱
                  </Button>
                </div>
                {reindexResult && (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                    {reindexResult}
                  </div>
                )}
                <p className="text-xs text-emerald-600/50">
                  重建索引会重新解析所有文档内容并生成分块；重建图谱会重新计算文档间引用关系。
                </p>
              </TabsContent>

              {/* Lint */}
              <TabsContent value="lint" className="mt-4 space-y-3">
                <Button onClick={runLint} disabled={lintBusy} className="bg-emerald-600 text-white hover:bg-emerald-500">
                  {lintBusy ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheckIcon className="size-4" />}
                  运行健康检查
                </Button>
                {lintReport && (
                  <Card className="border-emerald-100 bg-white/80">
                    <CardContent className="space-y-2 p-4">
                      <div className="flex gap-4 text-sm">
                        <span className="text-emerald-700">总计：{String(lintReport.total)}</span>
                        <span className="text-red-600">错误：{String(lintReport.errors)}</span>
                        <span className="text-amber-600">警告：{String(lintReport.warnings)}</span>
                      </div>
                      {Array.isArray(lintReport.issues) && lintReport.issues.length > 0 ? (
                        <div className="space-y-1">
                          {(lintReport.issues as Record<string, unknown>[]).map((iss, i) => (
                            <div
                              key={i}
                              className={cn(
                                "rounded-lg border px-3 py-2 text-sm",
                                iss.severity === "error"
                                  ? "border-red-200 bg-red-50 text-red-700"
                                  : "border-amber-200 bg-amber-50 text-amber-700"
                              )}
                            >
                              <span className="font-medium">[{String(iss.code)}]</span>{" "}
                              {String(iss.path)}：{String(iss.message)}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-sm text-emerald-600/60">无问题</p>
                      )}
                    </CardContent>
                  </Card>
                )}
              </TabsContent>

              {/* 订阅者 */}
              <TabsContent value="subs" className="mt-4 space-y-2">
                {subsLoading ? (
                  <div className="flex justify-center py-10 text-emerald-500">
                    <Loader2 className="size-5 animate-spin" />
                  </div>
                ) : subs.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-10 text-center text-emerald-600/50">
                    <UsersIcon className="size-8" />
                    <p className="text-sm">暂无订阅者</p>
                  </div>
                ) : (
                  subs.map((s) => (
                    <Card key={s.id} className="border-emerald-100 bg-white/80">
                      <CardContent className="flex items-center gap-3 p-4">
                        <div className="flex size-9 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-700">
                          {(s.user_name || s.user_phone || "?").slice(0, 1)}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-emerald-950">
                            {s.user_name || "未命名"}
                          </p>
                          <p className="truncate text-xs text-emerald-600/60">{s.user_phone}</p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="hover:bg-red-50 hover:text-red-600"
                          onClick={() => removeSub(s.user_id)}
                        >
                          <TrashIcon className="size-4" />
                        </Button>
                      </CardContent>
                    </Card>
                  ))
                )}
              </TabsContent>

              {/* 令牌 */}
              <TabsContent value="tokens" className="mt-4 space-y-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm text-emerald-600/60">外部 MCP 访问令牌（脱敏展示）</p>
                  <Button onClick={() => setTokenOpen(true)} className="bg-emerald-600 text-white hover:bg-emerald-500">
                    <PlusIcon className="size-4" />
                    新建令牌
                  </Button>
                </div>

                {createdToken && (
                  <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
                    <p className="mb-1 text-sm font-semibold text-amber-800">令牌已创建（仅此一次显示）</p>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 truncate rounded bg-white/70 px-2 py-1 text-xs text-amber-900">
                        {createdToken.token}
                      </code>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => navigator.clipboard?.writeText(createdToken.token)}
                      >
                        <CopyIcon className="size-4" />
                      </Button>
                    </div>
                  </div>
                )}

                {tokensLoading ? (
                  <div className="flex justify-center py-10 text-emerald-500">
                    <Loader2 className="size-5 animate-spin" />
                  </div>
                ) : tokens.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-10 text-center text-emerald-600/50">
                    <KeyIcon className="size-8" />
                    <p className="text-sm">暂无令牌</p>
                  </div>
                ) : (
                  tokens.map((t) => (
                    <Card key={t.id} className="border-emerald-100 bg-white/80">
                      <CardContent className="flex items-center gap-3 p-4">
                        <KeyIcon className="size-4 shrink-0 text-emerald-500" />
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium text-emerald-950">{t.name}</p>
                          <p className="truncate text-xs text-emerald-600/60">
                            {t.token_prefix}… · {t.scope}
                            {t.revoked_at && " · 已撤销"}
                          </p>
                        </div>
                        {!t.revoked_at && (
                          <Button
                            variant="ghost"
                            size="sm"
                            className="hover:bg-red-50 hover:text-red-600"
                            onClick={() => revokeToken(t.id)}
                          >
                            撤销
                          </Button>
                        )}
                      </CardContent>
                    </Card>
                  ))
                )}
              </TabsContent>
            </Tabs>
          )}
        </div>
      </div>

      {/* 新建文档弹窗 */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建文档</DialogTitle>
            <DialogDescription>创建后会自动分块索引</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-emerald-900">标题</label>
              <Input
                value={createForm.title}
                onChange={(e) => setCreateForm({ ...createForm, title: e.target.value })}
                placeholder="文档标题"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-emerald-900">文件名</label>
              <Input
                value={createForm.filename}
                onChange={(e) => setCreateForm({ ...createForm, filename: e.target.value })}
                placeholder="如：guide.md"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              {(["wiki", "raw"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setCreateForm({ ...createForm, source_kind: s })}
                  className={cn(
                    "rounded-lg border px-3 py-2 text-sm font-medium",
                    createForm.source_kind === s
                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                      : "border-emerald-100 text-emerald-600/70"
                  )}
                >
                  {s === "wiki" ? "Wiki" : "原始"}
                </button>
              ))}
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-emerald-900">内容（Markdown）</label>
              <Textarea
                value={createForm.content}
                onChange={(e) => setCreateForm({ ...createForm, content: e.target.value })}
                rows={8}
                placeholder="# 标题&#10;正文内容..."
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>取消</Button>
            <Button
              onClick={createDoc}
              disabled={creating || !createForm.title.trim() || !createForm.filename.trim()}
              className="bg-emerald-600 text-white hover:bg-emerald-500"
            >
              {creating && <Loader2 className="size-4 animate-spin" />}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 编辑内容弹窗 */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑文档内容</DialogTitle>
            <DialogDescription>
              {editDoc?.title}（乐观锁：基于版本 v{editContent?.version}）
            </DialogDescription>
          </DialogHeader>
          {editLoading ? (
            <div className="flex justify-center py-8 text-emerald-500">
              <Loader2 className="size-5 animate-spin" />
            </div>
          ) : (
            <Textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              rows={16}
              className="font-mono text-sm"
            />
          )}
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditOpen(false)}>取消</Button>
            <Button
              onClick={saveEdit}
              disabled={editSaving || editLoading}
              className="bg-emerald-600 text-white hover:bg-emerald-500"
            >
              {editSaving && <Loader2 className="size-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 新建令牌弹窗 */}
      <Dialog open={tokenOpen} onOpenChange={setTokenOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>新建 API 令牌</DialogTitle>
            <DialogDescription>明文令牌仅创建时显示一次</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-emerald-900">名称</label>
              <Input
                value={tokenForm.name}
                onChange={(e) => setTokenForm({ ...tokenForm, name: e.target.value })}
                placeholder="如：外部 Agent 接入"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              {(["read", "write"] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setTokenForm({ ...tokenForm, scope: s })}
                  className={cn(
                    "rounded-lg border px-3 py-2 text-sm font-medium",
                    tokenForm.scope === s
                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                      : "border-emerald-100 text-emerald-600/70"
                  )}
                >
                  {s === "read" ? "只读" : "读写"}
                </button>
              ))}
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setTokenOpen(false)}>取消</Button>
            <Button
              onClick={createToken}
              disabled={tokenCreating || !tokenForm.name.trim()}
              className="bg-emerald-600 text-white hover:bg-emerald-500"
            >
              {tokenCreating && <Loader2 className="size-4 animate-spin" />}
              创建
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
