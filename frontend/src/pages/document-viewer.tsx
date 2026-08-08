import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeftIcon, Loader2 } from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { buttonVariants } from "@/components/ui/button";
import { MessageResponse } from "@/components/ai-elements/message";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import {
  kbApi,
  type KBDocument,
  type KBDocumentContent,
  type KBDocumentReferences,
} from "@/lib/kb-api";

export default function DocumentViewerPage() {
  const { kbId = "", docId = "" } = useParams();
  const [doc, setDoc] = useState<KBDocumentContent | null>(null);
  const [meta, setMeta] = useState<KBDocument | null>(null);
  const [refs, setRefs] = useState<KBDocumentReferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    Promise.all([
      kbApi.readDocument(kbId, docId),
      kbApi.getDocument(kbId, docId),
      kbApi.getReferences(kbId, docId),
    ])
      .then(([d, m, r]) => {
        if (!alive) return;
        setDoc(d);
        setMeta(m);
        setRefs(r);
        setLoading(false);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e instanceof ApiError ? e.message : "加载文档失败");
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [kbId, docId]);

  const breadcrumbs = (meta?.path || "/").split("/").filter(Boolean);

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-5xl space-y-4 p-6">
          <div className="flex items-center gap-3">
            <Link
              to={`/knowledge-bases/${kbId}`}
              className={cn(buttonVariants({ variant: "ghost", size: "icon" }), "size-9")}
            >
              <ArrowLeftIcon className="size-4" />
            </Link>
            <div className="min-w-0">
              <h1 className="truncate text-xl font-bold text-emerald-950">
                {doc?.title ?? "文档"}
              </h1>
              {doc && (
                <p className="truncate text-sm text-emerald-600/60">
                  {doc.filename} · 版本 v{doc.version}
                </p>
              )}
            </div>
          </div>

          {meta?.stale_since && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
              该文档已过期（引用源可能已更新），建议重新索引。
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          ) : (
            <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
              <article className="rounded-2xl border border-emerald-100 bg-white p-6 shadow-sm">
                {breadcrumbs.length > 0 && (
                  <nav className="mb-3 flex flex-wrap items-center gap-1 text-xs text-emerald-500/70">
                    {breadcrumbs.map((b, i) => (
                      <span key={i} className="flex items-center gap-1">
                        {i > 0 && <span>/</span>}
                        <span>{b}</span>
                      </span>
                    ))}
                  </nav>
                )}
                <MessageResponse>{doc?.content ?? ""}</MessageResponse>
              </article>

              <aside className="space-y-4">
                {refs && (
                  <div className="rounded-xl border border-emerald-100 bg-white p-4 text-sm shadow-sm">
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
              </aside>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}