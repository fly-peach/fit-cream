import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BookOpenIcon,
  Loader2,
  SearchIcon,
  ArrowRightIcon,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import { kbApi, type KBListItem } from "@/lib/kb-api";

export default function KnowledgeBasesPage() {
  const [allKbs, setAllKbs] = useState<KBListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState("");

  const loadAll = useCallback(async () => {
    try {
      const list = await kbApi.list();
      setAllKbs(list);
      setError("");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载知识库失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const filterKbs = (list: KBListItem[]) => {
    const kw = keyword.trim().toLowerCase();
    if (!kw) return list;
    return list.filter(
      (k) =>
        k.name.toLowerCase().includes(kw) ||
        k.description.toLowerCase().includes(kw)
    );
  };

  const renderGrid = (list: KBListItem[]) => {
    const filtered = filterKbs(list);
    if (filtered.length === 0) {
      return (
        <div className="flex flex-col items-center gap-2 py-16 text-center text-emerald-600/50">
          <BookOpenIcon className="size-8" />
          <p className="text-sm">暂无知识库</p>
        </div>
      );
    }
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((kb) => (
          <Card
            key={kb.id}
            className="flex flex-col border-emerald-100 bg-white/80 transition-shadow hover:shadow-md"
          >
            <CardContent className="flex flex-1 flex-col gap-3 p-5">
              <h3 className="line-clamp-1 font-semibold text-emerald-950">
                {kb.name}
              </h3>
              <p className="line-clamp-2 flex-1 text-sm text-emerald-700/70">
                {kb.description || "暂无描述"}
              </p>
              <div className="flex items-center gap-2 pt-1">
                <Link
                  to={`/knowledge-bases/${kb.id}`}
                  className={cn(
                    buttonVariants({ variant: "ghost", size: "sm" }),
                    "text-emerald-700"
                  )}
                >
                  查看
                  <ArrowRightIcon className="size-3.5" />
                </Link>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-5xl space-y-6 p-6">
          <header className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-100">
              <BookOpenIcon className="size-5 text-emerald-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-emerald-950">知识库</h1>
              <p className="text-sm text-emerald-600/60">
                登录即可浏览全部知识库，AI 教练可在对话中检索其内容
              </p>
            </div>
          </header>

          <div className="relative">
            <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-emerald-400" />
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索知识库名称或描述"
              className="rounded-xl border-emerald-200 bg-white/70 pl-9"
            />
          </div>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : (
            renderGrid(allKbs)
          )}
        </div>
      </div>
    </AppLayout>
  );
}
