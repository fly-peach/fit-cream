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
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import { kbApi, type KBListItem } from "@/lib/kb-api";

type Tab = "all" | "mine";

export default function KnowledgeBasesPage() {
  const [allKbs, setAllKbs] = useState<KBListItem[]>([]);
  const [myKbs, setMyKbs] = useState<KBListItem[]>([]);
  const [tab, setTab] = useState<Tab>("all");
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [keyword, setKeyword] = useState("");

  const loadAll = useCallback(async () => {
    try {
      const [list, mine] = await Promise.all([kbApi.list(), kbApi.mySubscriptions()]);
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
    setBusyId(kb.id);
    setError("");
    try {
      if (kb.subscribed) {
        await kbApi.unsubscribe(kb.id);
      } else {
        await kbApi.subscribe(kb.id);
      }
      await loadAll();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "操作失败");
    } finally {
      setBusyId(null);
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
        <div className="flex flex-col items-center gap-1 py-6 text-center text-emerald-600/50 sm:gap-2 sm:py-16">
          <BookOpenIcon className="size-3 sm:size-8" />
          <p className="text-[6px] sm:text-sm">
            {tab === "mine" ? "还没有订阅任何知识库" : "暂无知识库"}
          </p>
        </div>
      );
    }
    return (
      <div className="grid grid-cols-3 gap-1 sm:gap-2">
        {filtered.map((kb) => (
          <Card
            key={kb.id}
            className="flex flex-col border-emerald-100 bg-white/80 transition-shadow hover:shadow-md"
          >
            <CardContent className="flex flex-1 flex-col gap-[2px] p-1 sm:gap-1.5 sm:p-2.5">
              <div className="flex items-start justify-between gap-1">
                <h3 className="line-clamp-1 text-[6px] font-semibold text-emerald-950 sm:text-sm">
                  {kb.name}
                </h3>
                {kb.subscribed && (
                  <span className="shrink-0 rounded-full bg-emerald-100 px-1 py-0.5 text-[4px] font-medium text-emerald-700 sm:px-1.5 sm:text-[10px]">
                    已订阅
                  </span>
                )}
              </div>
              <p className="line-clamp-1 flex-1 text-[5px] text-emerald-700/70 sm:text-xs">
                {kb.description || "暂无描述"}
              </p>
              <div className="flex items-center gap-[2px] pt-0.5 sm:gap-1">
                <Link
                  to={`/knowledge-bases/${kb.id}`}
                  className={cn(
                    buttonVariants({ variant: "ghost", size: "icon" }),
                    "size-3 text-emerald-700 sm:size-8"
                  )}
                  title="查看"
                >
                  <ArrowRightIcon className="size-[5px] sm:size-3.5" />
                </Link>
                <Button
                  variant={kb.subscribed ? "outline" : "default"}
                  size="sm"
                  disabled={busyId === kb.id}
                  onClick={() => toggleSubscribe(kb)}
                  className={cn(
                    "h-3 flex-1 px-1 text-[5px] sm:h-7 sm:px-2.5 sm:text-[0.8rem]",
                    kb.subscribed
                      ? "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                      : "bg-emerald-600 text-white hover:bg-emerald-500"
                  )}
                >
                  {busyId === kb.id ? (
                    <Loader2 className="size-[6px] animate-spin sm:size-3.5" />
                  ) : kb.subscribed ? (
                    <CheckIcon className="size-[6px] sm:size-3.5" />
                  ) : (
                    <PlusIcon className="size-[6px] sm:size-3.5" />
                  )}
                  <span className="ml-1">{kb.subscribed ? "已订阅" : "订阅"}</span>
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    );
  };

  const currentList = tab === "mine" ? myKbs : allKbs;

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-5xl space-y-2.5 p-2 sm:space-y-6 sm:p-6">
          <header className="flex items-center gap-1.5 sm:gap-3">
            <div className="flex size-[18px] shrink-0 items-center justify-center rounded-xl bg-emerald-100 sm:size-11 sm:rounded-2xl">
              <BookOpenIcon className="size-2 text-emerald-600 sm:size-5" />
            </div>
            <div>
              <h1 className="text-[8px] font-bold text-emerald-950 sm:text-xl">
                知识库
              </h1>
              <p className="text-[6px] text-emerald-600/60 sm:text-sm">
                订阅知识库后即可浏览其文档，AI 教练也会在对话中检索已订阅的知识库
              </p>
            </div>
          </header>

          <div className="flex items-center gap-1 sm:gap-2">
            <div className="flex rounded-lg bg-emerald-50 p-0.5 sm:rounded-xl sm:p-1">
              <button
                onClick={() => setTab("all")}
                className={cn(
                  "rounded-md px-1.5 py-1 text-[6px] font-medium transition-colors sm:rounded-lg sm:px-3 sm:py-1.5 sm:text-sm",
                  tab === "all"
                    ? "bg-white text-emerald-700 shadow-sm"
                    : "text-emerald-600/60 hover:text-emerald-700"
                )}
              >
                全部
              </button>
              <button
                onClick={() => setTab("mine")}
                className={cn(
                  "rounded-md px-1.5 py-1 text-[6px] font-medium transition-colors sm:rounded-lg sm:px-3 sm:py-1.5 sm:text-sm",
                  tab === "mine"
                    ? "bg-white text-emerald-700 shadow-sm"
                    : "text-emerald-600/60 hover:text-emerald-700"
                )}
              >
                我的订阅（{myKbs.length}）
              </button>
            </div>
          </div>

          <div className="relative">
            <SearchIcon className="pointer-events-none absolute left-2 top-1/2 size-2 -translate-y-1/2 text-emerald-400 sm:left-3 sm:size-4" />
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索知识库名称或描述"
              className="h-3 pl-5 text-[6px] sm:h-8 sm:pl-9 sm:text-sm"
            />
          </div>

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-2 py-1.5 text-[6px] text-red-600 sm:rounded-xl sm:px-4 sm:py-3 sm:text-sm">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-8 text-emerald-500 sm:py-20">
              <Loader2 className="size-3 animate-spin sm:size-6" />
            </div>
          ) : (
            renderGrid(currentList)
          )}
        </div>
      </div>
    </AppLayout>
  );
}