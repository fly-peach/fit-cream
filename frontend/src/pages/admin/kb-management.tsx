import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRightIcon,
  BookOpenIcon,
  Loader2,
  PencilIcon,
  PlusIcon,
  TrashIcon,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
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
  type KBVisibilityInput,
} from "@/lib/kb-api";

const VISIBILITY_LABEL: Record<string, string> = {
  private: "私有",
  shared: "共享",
  public: "公开",
};

const VIS_OPTIONS: { value: KBVisibilityInput["visibility"]; label: string }[] = [
  { value: "private", label: "私有" },
  { value: "shared", label: "共享" },
  { value: "public", label: "公开" },
];

interface EditState {
  id?: string;
  name: string;
  description: string;
}

export default function AdminKbManagementPage() {
  const [kbs, setKbs] = useState<KB[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [editOpen, setEditOpen] = useState(false);
  const [edit, setEdit] = useState<EditState>({ name: "", description: "" });
  const [saving, setSaving] = useState(false);

  const [visKb, setVisKb] = useState<KB | null>(null);
  const [visValue, setVisValue] = useState<KBVisibilityInput>({
    visibility: "private",
  });
  const [visSaving, setVisSaving] = useState(false);

  const [deleteKb, setDeleteKb] = useState<KB | null>(null);
  const [deleting, setDeleting] = useState(false);

  const load = useCallback(async () => {
    try {
      setKbs(await kbApi.list());
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

  const openCreate = () => {
    setEdit({ name: "", description: "" });
    setEditOpen(true);
  };

  const openEdit = (kb: KB) => {
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
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const openVis = (kb: KB) => {
    setVisKb(kb);
    setVisValue({ visibility: kb.visibility as KBVisibilityInput["visibility"], public_slug: kb.public_slug ?? undefined });
  };

  const saveVis = async () => {
    if (!visKb) return;
    setVisSaving(true);
    try {
      await kbApi.setVisibility(visKb.id, visValue);
      setVisKb(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "设置失败");
    } finally {
      setVisSaving(false);
    }
  };

  const confirmDelete = async () => {
    if (!deleteKb) return;
    setDeleting(true);
    try {
      await kbApi.remove(deleteKb.id);
      setDeleteKb(null);
      await load();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-5xl space-y-6 p-6">
          <header className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-100">
                <BookOpenIcon className="size-5 text-emerald-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-emerald-950">知识库管理</h1>
                <p className="text-sm text-emerald-600/60">创建、编辑、删除知识库及可见性</p>
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

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : kbs.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-16 text-center text-emerald-600/50">
              <BookOpenIcon className="size-8" />
              <p className="text-sm">暂无知识库，点击「新建」创建</p>
            </div>
          ) : (
            <div className="space-y-2">
              {kbs.map((kb) => (
                <Card key={kb.id} className="border-emerald-100 bg-white/80">
                  <CardContent className="flex items-center gap-3 p-4">
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <p className="truncate font-semibold text-emerald-950">
                          {kb.name}
                        </p>
                        <button
                          onClick={() => openVis(kb)}
                          className="shrink-0"
                          title="设置可见性"
                        >
                          <Badge
                            variant="outline"
                            className="cursor-pointer border-emerald-200 text-emerald-600 hover:bg-emerald-50"
                          >
                            {VISIBILITY_LABEL[kb.visibility] ?? kb.visibility}
                          </Badge>
                        </button>
                      </div>
                      <p className="line-clamp-1 text-sm text-emerald-600/60">
                        {kb.description || "暂无描述"}
                      </p>
                    </div>
                    <div className="flex items-center gap-1">
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
                        className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "text-emerald-700")}
                      >
                        管理
                        <ArrowRightIcon className="size-3.5" />
                      </Link>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
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

      {/* 可见性弹窗 */}
      <Dialog open={!!visKb} onOpenChange={(o) => !o && setVisKb(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>设置可见性</DialogTitle>
            <DialogDescription>
              可见性仅控制外部访问（MCP token / 公开链接），不影响内部用户只读访问。
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-3 gap-2">
              {VIS_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() =>
                    setVisValue({ ...visValue, visibility: opt.value })
                  }
                  className={cn(
                    "rounded-lg border px-3 py-2 text-sm font-medium transition-colors",
                    visValue.visibility === opt.value
                      ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                      : "border-emerald-100 text-emerald-600/70 hover:bg-emerald-50/50"
                  )}
                >
                  {opt.label}
                </button>
              ))}
            </div>
            {visValue.visibility === "public" && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-emerald-900">
                  公开 Slug（全局唯一）
                </label>
                <Input
                  value={visValue.public_slug ?? ""}
                  onChange={(e) =>
                    setVisValue({ ...visValue, public_slug: e.target.value })
                  }
                  placeholder="如：fitness-basics"
                />
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setVisKb(null)}>
              取消
            </Button>
            <Button
              onClick={saveVis}
              disabled={visSaving || (visValue.visibility === "public" && !visValue.public_slug)}
              className="bg-emerald-600 text-white hover:bg-emerald-500"
            >
              {visSaving && <Loader2 className="size-4 animate-spin" />}
              确认
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
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleting}
            >
              {deleting && <Loader2 className="size-4 animate-spin" />}
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AppLayout>
  );
}
