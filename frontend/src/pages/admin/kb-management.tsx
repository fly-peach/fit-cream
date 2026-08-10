import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { format, parseISO } from "date-fns";
import { zhCN } from "date-fns/locale";
import {
  ArrowRightIcon,
  BookOpenIcon,
  Loader2,
  PencilIcon,
  PlusIcon,
  SearchIcon,
  TrashIcon,
} from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card } from "@/components/ui/card";
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
import { kbApi } from "@/lib/kb-api";
import { adminApi, type AdminKbListItem } from "@/lib/admin-api";
import { showError, showSuccess } from "@/lib/toast";

const PAGE_SIZE = 20;

interface EditState {
  id?: string;
  name: string;
  description: string;
}

export default function AdminKbManagementPage() {
  const [kbs, setKbs] = useState<AdminKbListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [editOpen, setEditOpen] = useState(false);
  const [edit, setEdit] = useState<EditState>({ name: "", description: "" });
  const [saving, setSaving] = useState(false);

  const [deleteKb, setDeleteKb] = useState<AdminKbListItem | null>(null);
  const [deleting, setDeleting] = useState(false);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await adminApi.listKbs({
        page,
        size: PAGE_SIZE,
        keyword: keyword.trim() || undefined,
      });
      setKbs(data.items);
      setTotal(data.total);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [page, keyword]);

  useEffect(() => {
    load();
  }, [load]);

  const openCreate = () => {
    setEdit({ name: "", description: "" });
    setEditOpen(true);
  };

  const openEdit = (kb: AdminKbListItem) => {
    setEdit({ id: kb.id, name: kb.name, description: kb.description });
    setEditOpen(true);
  };

  const save = async () => {
    if (!edit.name.trim()) return;
    setSaving(true);
    try {
      if (edit.id) {
        await kbApi.update(edit.id, {
          name: edit.name,
          description: edit.description,
        });
      } else {
        await kbApi.create({
          name: edit.name,
          description: edit.description,
        });
      }
      setEditOpen(false);
      showSuccess(edit.id ? "已保存" : "已创建");
      await load();
    } catch (e) {
      showError(e instanceof ApiError ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteKb) return;
    setDeleting(true);
    try {
      await kbApi.remove(deleteKb.id);
      setDeleteKb(null);
      showSuccess("已删除");
      await load();
    } catch (e) {
      showError(e instanceof ApiError ? e.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-6 p-6">
        <header className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-100">
              <BookOpenIcon className="size-5 text-emerald-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-emerald-950">知识库管理</h1>
              <p className="text-sm text-emerald-600/60">
                创建、编辑、删除知识库，查看文档与索引状态
              </p>
            </div>
          </div>
          <Button
            onClick={openCreate}
            className="bg-emerald-600 text-white hover:bg-emerald-500"
          >
            <PlusIcon className="size-4" />
            新建
          </Button>
        </header>

        <div className="relative">
          <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-emerald-400" />
          <Input
            value={keyword}
            onChange={(e) => {
              setKeyword(e.target.value);
              setPage(1);
            }}
            placeholder="搜索知识库名称或 slug"
            className="max-w-md rounded-xl border-emerald-200 bg-white/70 pl-9"
          />
        </div>

        {error && (
          <div className="flex items-center justify-between rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
            <span>{error}</span>
            <button onClick={() => setError("")} className="text-red-400">
              ✕
            </button>
          </div>
        )}

        <Card className="border-emerald-100 bg-white/80">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] text-left text-sm">
              <thead>
                <tr className="border-b border-emerald-100 text-xs text-emerald-600/60">
                  <th className="px-4 py-3 font-medium">名称</th>
                  <th className="px-4 py-3 font-medium">slug</th>
                  <th className="px-4 py-3 font-medium">描述</th>
                  <th className="px-4 py-3 font-medium">文档数</th>
                  <th className="px-4 py-3 font-medium">分块数</th>
                  <th className="px-4 py-3 font-medium">待索引</th>
                  <th className="px-4 py-3 font-medium">创建人</th>
                  <th className="px-4 py-3 font-medium">创建时间</th>
                  <th className="px-4 py-3 text-right font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-16 text-center text-emerald-500">
                      <Loader2 className="mx-auto size-5 animate-spin" />
                    </td>
                  </tr>
                ) : kbs.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-16 text-center text-sm text-emerald-600/50">
                      暂无知识库，点击「新建」创建
                    </td>
                  </tr>
                ) : (
                  kbs.map((kb) => (
                    <tr
                      key={kb.id}
                      className="border-b border-emerald-50 last:border-0 hover:bg-emerald-50/30"
                    >
                      <td className="max-w-44 px-4 py-3">
                        <p className="truncate font-medium text-emerald-950">{kb.name}</p>
                      </td>
                      <td className="px-4 py-3 font-mono text-xs text-emerald-600/70">
                        {kb.slug}
                      </td>
                      <td className="max-w-48 px-4 py-3">
                        <p className="line-clamp-1 text-xs text-emerald-600/60">
                          {kb.description || "暂无描述"}
                        </p>
                      </td>
                      <td className="px-4 py-3 tabular-nums text-emerald-900">
                        {kb.document_count}
                      </td>
                      <td className="px-4 py-3 tabular-nums text-emerald-900">
                        {kb.chunk_count}
                      </td>
                      <td className="px-4 py-3">
                        {kb.pending_document_count > 0 ? (
                          <span className="text-amber-600 tabular-nums">
                            {kb.pending_document_count}
                          </span>
                        ) : (
                          <span className="text-emerald-500">0</span>
                        )}
                      </td>
                      <td className="max-w-28 px-4 py-3">
                        <p className="truncate text-xs text-emerald-700">
                          {kb.owner_name || "—"}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-xs text-emerald-600/70">
                        {format(parseISO(kb.created_at), "yyyy-MM-dd", {
                          locale: zhCN,
                        })}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="icon" onClick={() => openEdit(kb)}>
                            <PencilIcon className="size-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="hover:bg-red-50 hover:text-red-600"
                            onClick={() => setDeleteKb(kb)}
                          >
                            <TrashIcon className="size-4" />
                          </Button>
                          <Link
                            to={`/admin/knowledge-bases/${kb.id}`}
                            className={cn(
                              buttonVariants({ variant: "ghost", size: "sm" }),
                              "text-emerald-700"
                            )}
                          >
                            管理
                            <ArrowRightIcon className="size-3.5" />
                          </Link>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>

        {!loading && total > 0 && (
          <div className="flex items-center justify-between text-sm text-emerald-600/60">
            <span>
              共 {total} 个知识库 · 第 {page} / {totalPages} 页
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                上一页
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              >
                下一页
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* 创建/编辑弹窗 */}
      <Dialog open={editOpen} onOpenChange={setEditOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{edit.id ? "编辑知识库" : "新建知识库"}</DialogTitle>
            <DialogDescription>设置知识库名称与描述</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <label className="text-sm font-medium text-emerald-900">名称</label>
              <Input
                value={edit.name}
                onChange={(e) => setEdit({ ...edit, name: e.target.value })}
                placeholder="如：健身基础知识库"
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-emerald-900">描述</label>
              <Textarea
                value={edit.description}
                onChange={(e) => setEdit({ ...edit, description: e.target.value })}
                placeholder="知识库用途说明"
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditOpen(false)}>
              取消
            </Button>
            <Button
              onClick={save}
              disabled={saving || !edit.name.trim()}
              className="bg-emerald-600 text-white hover:bg-emerald-500"
            >
              {saving && <Loader2 className="size-4 animate-spin" />}
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* 删除确认 */}
      <Dialog open={!!deleteKb} onOpenChange={(o) => !o && setDeleteKb(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除知识库</DialogTitle>
            <DialogDescription>
              确定删除「{deleteKb?.name}」吗？此操作不可恢复，所有文档与索引将被删除。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setDeleteKb(null)}>
              取消
            </Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>
              {deleting && <Loader2 className="size-4 animate-spin" />}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
