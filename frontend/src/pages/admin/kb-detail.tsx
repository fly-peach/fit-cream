import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeftIcon,
  FileTextIcon,
  Loader2,
  PlusIcon,
  RefreshCwIcon,
  TrashIcon,
  UsersIcon,
} from "lucide-react";
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
  });
  const [creating, setCreating] = useState(false);

  // 文档编辑
  const [editOpen, setEditOpen] = useState(false);
  const [editDoc, setEditDoc] = useState<KBDocument | null>(null);
  const [editContent, setEditContent] = useState<KBDocumentContent | null>(null);
  const [editText, setEditText] = useState("");
  const [editSaving, setEditSaving] = useState(false);
  const [editLoading, setEditLoading] = useState(false);

  // 索引 + lint（重建并检查）
  const [reindexResult, setReindexResult] = useState<string>("");
  const [indexBusy, setIndexBusy] = useState(false);
  const [lintReport, setLintReport] = useState<Record<string, unknown> | null>(null);

  // 订阅者
  const [subs, setSubs] = useState<KBSubscription[]>([]);
  const [subsLoading, setSubsLoading] = useState(false);

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
      });
      setCreateOpen(false);
      setCreateForm({ title: "", filename: "", content: "" });
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

  // ---------- 重建并检查 ----------
  const handleRebuildLint = async () => {
    setIndexBusy(true);
    try {
      const r = await kbApi.rebuildLint(kbId);
      const rebuilt = (r.rebuilt ?? {}) as Record<string, unknown>;
      setReindexResult(
        `已重建索引（处理 ${String(rebuilt.documents_processed ?? 0)} 文档，生成 ${String(
          rebuilt.chunks_created ?? 0
        )} 分块）与引用图`
      );
      setLintReport(r.lint);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "重建失败");
    } finally {
      setIndexBusy(false);
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

  return (
    <>
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
              <p className="text-sm text-emerald-600/60">管理文档与索引</p>
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
                <TabsTrigger value="index">索引与检查</TabsTrigger>
                <TabsTrigger value="subs" onClick={loadSubs}>订阅者</TabsTrigger>
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
                            {d.filename} · v{d.version}
                            {d.status === "pending" && " · 待索引"}
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

              {/* 索引与检查 */}
              <TabsContent value="index" className="mt-4 space-y-4">
                <Button
                  onClick={handleRebuildLint}
                  disabled={indexBusy}
                  className="bg-emerald-600 text-white hover:bg-emerald-500"
                >
                  {indexBusy ? (
                    <Loader2 className="size-4 animate-spin" />
                  ) : (
                    <RefreshCwIcon className="size-4" />
                  )}
                  重建并检查
                </Button>
                {reindexResult && (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
                    {reindexResult}
                  </div>
                )}
                <p className="text-xs text-emerald-600/50">
                  重建会统一生成搜索索引（分块+向量）、重建文档引用图，并运行健康检查。写入文档后请点击此按钮生效。
                </p>
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
                          title="移除订阅者"
                        >
                          <TrashIcon className="size-4" />
                        </Button>
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
            <DialogDescription>创建后需在「索引与检查」点击「重建并检查」生成索引</DialogDescription>
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
    </>
  );
}
