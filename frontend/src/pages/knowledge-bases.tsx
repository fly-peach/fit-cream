import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BookOpenIcon,
  CheckIcon,
  Loader2,
  PlusIcon,
  SearchIcon,
  ArrowRightIcon,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { Button, buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import { kbApi, type KBListItem } from "@/lib/kb-api";

const VISIBILITY_LABEL: Record<string, string> = {
  private: "私有",
  shared: "共享",
  public: "公开",
};

export default function KnowledgeBasesPage() {
  const [allKbs, setAllKbs] = useState<KBListItem[]>([]);
  const [myKbs, setMyKbs] = useState<KBListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState("");
  const [toggling, setToggling] = useState<string | null>(null);

  const loadAll = useCallback(async () => {
    try {
      const [list, mine] = await Promise.all([
        kbApi.list(),
        kbApi.mySubscriptions(),
      ]);
      setAllKbs(list);
      setMyKbs(mine);
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

  const toggleSubscribe = async (kb: KBListItem) => {
    setToggling(kb.id);
    const wasSubscribed = kb.subscribed;
    // 乐观更新
    setAllKbs((prev) =>
      prev.map((k) => (k.id === kb.id ? { ...k, subscribed: !wasSubscribed } : k))
    );
    try {
      if (wasSubscribed) {
        await kbApi.unsubscribe(kb.id);
        setMyKbs((prev) => prev.filter((k) => k.id !== kb.id));
      } else {
        await kbApi.subscribe(kb.id);
        setMyKbs((prev) => [
          { ...kb, subscribed: true },
          ...prev.filter((k) => k.id !== kb.id),
        ]);
      }
    } catch (e) {
      // 回滚
      setAllKbs((prev) =>
        prev.map((k) => (k.id === kb.id ? { ...k, subscribed: wasSubscribed } : k))
      );
      setError(e instanceof ApiError ? e.message : "操作失败");
    } finally {
      setToggling(null);
    }
  };

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
              <div className="flex items-start justify-between gap-2">
                <h3 className="line-clamp-1 font-semibold text-emerald-950">
                  {kb.name}
                </h3>
                <Badge
                  variant="outline"
                  className="shrink-0 border-emerald-200 text-emerald-600"
                >
                  {VISIBILITY_LABEL[kb.visibility] ?? kb.visibility}
                </Badge>
              </div>
              <p className="line-clamp-2 flex-1 text-sm text-emerald-700/70">
                {kb.description || "暂无描述"}
              </p>
              <div className="flex items-center gap-2 pt-1">
                <Button
                  variant={kb.subscribed ? "outline" : "default"}
                  size="sm"
                  disabled={toggling === kb.id}
                  onClick={() => toggleSubscribe(kb)}
                  className={cn(
                    kb.subscribed
                      ? "border-emerald-200 text-emerald-700"
                      : "bg-emerald-600 text-white hover:bg-emerald-500"
                  )}
                >
                  {toggling === kb.id ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : kb.subscribed ? (
                    <>
                      <CheckIcon className="size-3.5" />
                      已订阅
                    </>
                  ) : (
                    <>
                      <PlusIcon className="size-3.5" />
                      订阅
                    </>
                  )}
                </Button>
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
                订阅知识库后，AI 教练可在对话中检索其内容
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
            <Tabs defaultValue="all">
              <TabsList className="bg-emerald-50">
                <TabsTrigger value="all">
                  全部（{allKbs.length}）
                </TabsTrigger>
                <TabsTrigger value="mine">
                  我的订阅（{myKbs.length}）
                </TabsTrigger>
              </TabsList>
              <TabsContent value="all" className="mt-4">
                {renderGrid(allKbs)}
              </TabsContent>
              <TabsContent value="mine" className="mt-4">
                {renderGrid(myKbs)}
              </TabsContent>
            </Tabs>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
