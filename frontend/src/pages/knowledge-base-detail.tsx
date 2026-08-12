import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeftIcon,
  FileTextIcon,
  Loader2,
  SearchIcon,
  Share2Icon,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { KBGraph } from "@/components/kb-graph";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import {
  kbApi,
  type KB,
  type KBDocument,
  type KBSearchResult,
  type KBGraphData,
} from "@/lib/kb-api";

export default function KnowledgeBaseDetailPage() {
  const { kbId = "" } = useParams();
  const [kb, setKb] = useState<KB | null>(null);
  const [docs, setDocs] = useState<KBDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [query, setQuery] = useState("");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<KBSearchResult[]>([]);

  const [graph, setGraph] = useState<KBGraphData | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);

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
      setError(e instanceof ApiError ? e.message : "加载知识库失败");
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    load();
  }, [load]);

  const runSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    try {
      const r = await kbApi.search(kbId, query.trim());
      setResults(r);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "搜索失败");
    } finally {
      setSearching(false);
    }
  };

  const loadGraph = async () => {
    setGraphLoading(true);
    try {
      setGraph(await kbApi.getGraph(kbId));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载图谱失败");
    } finally {
      setGraphLoading(false);
    }
  };

  const requestGraphMode = async (mode: "full" | "overview") => {
    setGraphLoading(true);
    try {
      setGraph(await kbApi.getGraph(kbId, mode));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "加载图谱失败");
    } finally {
      setGraphLoading(false);
    }
  };

  const [tab, setTab] = useState("docs");

  const handleTabChange = (value: string) => {
    setTab(value);
    if (value === "graph") void loadGraph();
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
          <div className={cn("mx-auto space-y-6 p-6", tab === "graph" ? "max-w-6xl" : "max-w-5xl")}>
          <div className="flex items-center gap-3">
            <Link
              to="/knowledge-bases"
              className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "size-9")}
            >
              <ArrowLeftIcon className="size-4" />
            </Link>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <h1 className="truncate text-xl font-bold text-emerald-950">
                  {kb?.name ?? "知识库"}
                </h1>
              </div>
              <p className="line-clamp-1 text-sm text-emerald-600/60">
                {kb?.description || "暂无描述"}
              </p>
            </div>
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
            <Tabs value={tab} onValueChange={handleTabChange}>
              <TabsList className="bg-emerald-50">
                <TabsTrigger value="docs">文档（{docs.length}）</TabsTrigger>
                <TabsTrigger value="graph">图谱</TabsTrigger>
                <TabsTrigger value="search">搜索</TabsTrigger>
              </TabsList>

              {/* 文档列表（只读） */}
              <TabsContent value="docs" className="mt-4 space-y-2">
                {docs.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-16 text-center text-emerald-600/50">
                    <FileTextIcon className="size-8" />
                    <p className="text-sm">暂无文档</p>
                  </div>
                ) : (
                  docs.map((d) => (
                    <Link
                      key={d.id}
                      to={`/knowledge-bases/${kbId}/documents/${d.id}`}
                      className="flex items-center gap-3 rounded-xl border border-emerald-100 bg-white/80 p-4 transition-colors hover:bg-emerald-50/50"
                    >
                      <div className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-emerald-100">
                        <FileTextIcon className="size-4 text-emerald-600" />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium text-emerald-950">
                          {d.title}
                        </p>
                        <p className="truncate text-xs text-emerald-600/60">
                          {d.filename}{d.status === "pending" && " · 待索引"}
                        </p>
                      </div>
                      {d.stale_since && (
                        <Badge className="bg-amber-100 text-amber-700">已过期</Badge>
                      )}
                    </Link>
                  ))
                )}
              </TabsContent>

              {/* 全文搜索（只读） */}
              <TabsContent value="search" className="mt-4 space-y-4">
                <form onSubmit={runSearch} className="relative">
                  <SearchIcon className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-emerald-400" />
                  <Input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="输入关键词搜索文档内容"
                    className="rounded-xl border-emerald-200 bg-white/70 pl-9"
                  />
                </form>
                {searching ? (
                  <div className="flex items-center justify-center py-10 text-emerald-500">
                    <Loader2 className="size-5 animate-spin" />
                  </div>
                ) : results.length > 0 ? (
                  <div className="space-y-3">
                    {results.map((r) => (
                      <Card key={r.chunk_id} className="border-emerald-100 bg-white/80">
                        <CardContent className="space-y-1 p-4">
                          <Link
                            to={`/knowledge-bases/${kbId}/documents/${r.document_id}`}
                            className="text-sm font-semibold text-emerald-700 hover:underline"
                          >
                            {r.document_title}
                          </Link>
                          <p className="line-clamp-3 text-sm text-emerald-800/80">
                            {r.content}
                          </p>
                          {r.header_breadcrumb && (
                            <p className="text-xs text-emerald-500/70">
                              {r.header_breadcrumb}
                            </p>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                  </div>
                ) : query.trim() ? (
                  <p className="py-10 text-center text-sm text-emerald-600/50">
                    未找到匹配内容
                  </p>
                ) : null}
              </TabsContent>

              {/* 图谱（只读） */}
              <TabsContent value="graph" className="mt-4">
                {graphLoading ? (
                  <div className="flex items-center justify-center py-10 text-emerald-500">
                    <Loader2 className="size-5 animate-spin" />
                  </div>
                ) : graph ? (
                  <div className="space-y-4">
                    <div className="flex items-center gap-2 text-sm text-emerald-700">
                      <Share2Icon className="size-4" />
                      <span>
                        {graph.nodes.length} 个文档 · {graph.edges.length} 条引用
                      </span>
                    </div>
                    {graph.nodes.length === 0 ? (
                      <p className="py-6 text-center text-sm text-emerald-600/50">
                        暂无图谱数据
                      </p>
                    ) : (
                      <KBGraph
                        kbId={kbId}
                        graph={graph}
                        onRequestMode={requestGraphMode}
                      />
                    )}
                  </div>
                ) : null}
              </TabsContent>
            </Tabs>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
