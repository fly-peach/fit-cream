import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeftIcon, Loader2 } from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { buttonVariants } from "@/components/ui/button";
import { MessageResponse } from "@/components/ai-elements/message";
import { cn } from "@/lib/utils";
import { ApiError } from "@/lib/api";
import { kbApi, type KBDocumentContent } from "@/lib/kb-api";

export default function DocumentViewerPage() {
  const { kbId = "", docId = "" } = useParams();
  const [doc, setDoc] = useState<KBDocumentContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    kbApi
      .readDocument(kbId, docId)
      .then((d) => alive && (setDoc(d), setLoading(false)))
      .catch((e) => {
        if (!alive) return;
        setError(e instanceof ApiError ? e.message : "加载文档失败");
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [kbId, docId]);

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-3xl space-y-4 p-6">
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

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          ) : (
            <article className="rounded-2xl border border-emerald-100 bg-white p-6 shadow-sm">
              <MessageResponse>{doc?.content ?? ""}</MessageResponse>
            </article>
          )}
        </div>
      </div>
    </AppLayout>
  );
}
