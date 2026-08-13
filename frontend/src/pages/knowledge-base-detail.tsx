import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeftIcon,
  FileTextIcon,
  Loader2,
  SearchIcon,
  Share2Icon,
  XIcon,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { buttonVariants } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { KBGraph } from "@/components/kb-graph";
import { MessageResponse } from "@/components/ai-elements/message";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import {
  kbApi,
  type KB,
  type KBDocument,
  type KBDocumentContent,
  type KBDocumentReferences,
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

  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);
  const [article, setArticle] = useState<KBDocumentContent | null>(null);
  const [articleLoading, setArticleLoading] = useState(false);
  const [refs, setRefs] = useState<KBDocumentReferences | null>(null);

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

  const selectNode = useCallback(
    async (docId: string | null) => {
      setSelectedDocId(docId);
      setArticle(null);
      setRefs(null);
      if (!docId) return;
      setArticleLoading(true);
      try {
        const [r, a] = await Promise.all([
          kbApi.getReferences(kbId, docId),
          kbApi.readDocument(kbId, docId),
        ]);
        setRefs(r);
        setArticle(a);
      } catch {
        setArticle(null);
        setRefs(null);
      } finally {
        setArticleLoading(false);
      }
    },
    [kbId]
  );

  const [tab, setTab] = useState("docs");

  const handleTabChange = (value: string) => {
    setTab(value);
    if (value === "graph") void loadGraph();
    else void selectNode(null);
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
                        graph={graph}
                        selected={selectedDocId}
                        onSelectNode={selectNode}
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

      {selectedDocId && (
        <div className="fixed inset-y-0 right-0 z-40 flex w-[420px] max-w-[85vw] flex-col border-l border-slate-200 bg-white shadow-2xl">
          <div className="flex items-start justify-between gap-2 border-b border-slate-100 p-4">
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold text-emerald-950">
                {article?.title ?? "文档"}
              </p>
              {article && (
                <p className="truncate text-xs text-slate-500">
                  {article.filename} · v{article.version}
                </p>
              )}
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <Link
                to={`/knowledge-bases/${kbId}/documents/${selectedDocId}`}
                className="text-xs text-emerald-600 hover:underline"
              >
                打开全文
              </Link>
              <button
                onClick={() => void selectNode(null)}
                className="text-xs text-slate-400 hover:text-slate-600"
                title="关闭"
              >
                <XIcon className="size-4" />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-y-auto p-4">
            {articleLoading ? (
              <div className="flex items-center justify-center py-10 text-emerald-500">
                <Loader2 className="size-5 animate-spin" />
              </div>
            ) : article ? (
              <article className="text-sm leading-relaxed text-slate-700">
                <MessageResponse>{article.content}</MessageResponse>
              </article>
            ) : (
              <p className="py-8 text-center text-sm text-slate-400">加载文章失败</p>
            )}
          </div>

          {refs && (
            <div className="border-t border-slate-100 p-4 text-sm">
              <p className="mb-2 font-semibold text-emerald-900">引用关系</p>
              <div className="space-y-3 text-xs text-slate-600">
                <div>
                  <p className="mb-1 font-medium">引用了谁</p>
                  <ul className="space-y-1">
                    {refs.cites.length === 0 && refs.links_to.length === 0 ? (
                      <li className="text-slate-400">无</li>
                    ) : (
                      [...refs.cites, ...refs.links_to].map((r) => (
                        <li key={r.id}>
                          <Link
                            to={`/knowledge-bases/${kbId}/documents/${r.document_id}`}
                            className="text-emerald-600 hover:underline"
                          >
                            {r.title}
                          </Link>
                        </li>
                      ))
                    )}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 font-medium">被谁引用</p>
                  <ul className="space-y-1">
                    {refs.cited_by.length === 0 && refs.linked_by.length === 0 ? (
                      <li className="text-slate-400">无</li>
                    ) : (
                      [...refs.cited_by, ...refs.linked_by].map((r) => (
                        <li key={r.id}>
                          <Link
                            to={`/knowledge-bases/${kbId}/documents/${r.document_id}`}
                            className="text-emerald-600 hover:underline"
                          >
                            {r.title}
                          </Link>
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </AppLayout>
  );
}
