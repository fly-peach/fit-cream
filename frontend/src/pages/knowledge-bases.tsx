import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  BookOpenIcon,
  CheckIcon,
  Loader2,
  PlusIcon,
  SearchIcon,
  ArrowRightIcon,
  FileTextIcon,
  UserIcon,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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

  const renderEmpty = (isMine: boolean) => (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 flex size-16 items-center justify-center rounded-full bg-emerald-50">
        <BookOpenIcon className="size-8 text-emerald-400" />
      </div>
      <p className="mb-1 text-sm font-medium text-gray-700">
        {isMine ? "还没有订阅任何知识库" : "暂无知识库"}
      </p>
      <p className="text-xs text-gray-400">
        {isMine
          ? "去「全部」浏览并订阅感兴趣的知识库吧"
          : "知识库正在建设中，敬请期待"}
      </p>
    </div>
  );

  const renderGrid = (list: KBListItem[]) => {
    const filtered = filterKbs(list);
    if (filtered.length === 0) {
      return keyword.trim() ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="mb-4 flex size-16 items-center justify-center rounded-full bg-gray-50">
            <SearchIcon className="size-8 text-gray-300" />
          </div>
          <p className="text-sm font-medium text-gray-600">未找到相关知识库</p>
          <p className="text-xs text-gray-400">试试其他关键词</p>
        </div>
      ) : (
        renderEmpty(tab === "mine")
      );
    }
    return (
      <div className="grid grid-cols-2 gap-3">
        {filtered.map((kb) => (
          <div
            key={kb.id}
            className={cn(
              "group relative flex flex-col overflow-hidden rounded-2xl border bg-white transition-all duration-200",
              kb.subscribed
                ? "border-emerald-200 shadow-sm"
                : "border-gray-100 shadow-sm hover:shadow-md"
            )}
          >
            {kb.subscribed && (
              <div className="absolute right-0 top-0">
                <div className="rounded-bl-xl bg-emerald-500 px-2 py-0.5">
                  <CheckIcon className="size-3 text-white" />
                </div>
              </div>
            )}

            <div className="flex flex-1 flex-col p-3.5">
              <div className="mb-2 flex items-start gap-2">
                <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500">
                  <BookOpenIcon className="size-4 text-white" />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="line-clamp-2 text-sm font-semibold leading-tight text-gray-900">
                    {kb.name}
                  </h3>
                </div>
              </div>

              <p className="mb-3 line-clamp-2 flex-1 text-xs leading-relaxed text-gray-500">
                {kb.description || "暂无描述"}
              </p>

              <div className="flex items-center gap-2">
                <Link
                  to={`/knowledge-bases/${kb.id}`}
                  className={cn(
                    buttonVariants({ variant: "ghost", size: "icon" }),
                    "size-7 rounded-lg text-gray-400 hover:bg-gray-50 hover:text-emerald-600"
                  )}
                  title="查看详情"
                >
                  <ArrowRightIcon className="size-3.5" />
                </Link>
                <Button
                  variant={kb.subscribed ? "outline" : "default"}
                  size="sm"
                  disabled={busyId === kb.id}
                  onClick={() => toggleSubscribe(kb)}
                  className={cn(
                    "h-7 flex-1 rounded-lg px-2 text-xs font-medium transition-all",
                    kb.subscribed
                      ? "border-emerald-200 bg-emerald-50 text-emerald-600 hover:bg-emerald-100"
                      : "bg-emerald-500 text-white hover:bg-emerald-600 active:scale-[0.97]"
                  )}
                >
                  {busyId === kb.id ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : kb.subscribed ? (
                    <CheckIcon className="size-3.5" />
                  ) : (
                    <PlusIcon className="size-3.5" />
                  )}
                  <span className="ml-1">{kb.subscribed ? "已订阅" : "订阅"}</span>
                </Button>
              </div>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const currentList = tab === "mine" ? myKbs : allKbs;

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto bg-gray-50/50">
        <div className="mx-auto max-w-2xl px-4 pb-6 pt-4">
          {/* Header */}
          <header className="mb-5">
            <div className="mb-1 flex items-center gap-2.5">
              <div className="flex size-9 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 shadow-sm">
                <BookOpenIcon className="size-5 text-white" />
              </div>
              <h1 className="text-lg font-bold text-gray-900">知识库</h1>
            </div>
            <p className="text-xs leading-relaxed text-gray-400">
              订阅知识库后即可浏览其文档，AI 教练也会在对话中检索已订阅的知识库
            </p>
          </header>

          {/* Tabs */}
          <div className="mb-4 flex items-center gap-1 rounded-xl bg-gray-100 p-1">
            <button
              onClick={() => setTab("all")}
              className={cn(
                "flex-1 rounded-lg py-2 text-sm font-medium transition-all duration-200",
                tab === "all"
                  ? "bg-white text-emerald-600 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              )}
            >
              全部
            </button>
            <button
              onClick={() => setTab("mine")}
              className={cn(
                "flex-1 rounded-lg py-2 text-sm font-medium transition-all duration-200",
                tab === "mine"
                  ? "bg-white text-emerald-600 shadow-sm"
                  : "text-gray-500 hover:text-gray-700"
              )}
            >
              我的订阅
              {myKbs.length > 0 && (
                <span
                  className={cn(
                    "ml-1 inline-flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-semibold",
                    tab === "mine"
                      ? "bg-emerald-100 text-emerald-600"
                      : "bg-gray-200 text-gray-500"
                  )}
                >
                  {myKbs.length}
                </span>
              )}
            </button>
          </div>

          {/* Search */}
          <div className="relative mb-4">
            <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-gray-400" />
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索知识库名称或描述"
              className="h-10 rounded-xl border-gray-200 bg-white pl-9 text-sm shadow-sm transition-shadow focus:shadow-md focus-visible:ring-emerald-200"
            />
          </div>

          {/* Error */}
          {error && (
            <div className="mb-4 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {/* Content */}
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="size-6 animate-spin text-emerald-500" />
            </div>
          ) : (
            renderGrid(currentList)
          )}
        </div>
      </div>
    </AppLayout>
  );
}
