import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Background,
  Controls,
  MarkerType,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import {
  kbApi,
  type KBGraphData,
  type KBDocumentReferences,
} from "@/lib/kb-api";

const GROUP_COLORS: Record<string, string> = {
  训练动作: "#059669",
  饮食营养: "#ea580c",
  康复拉伸: "#0284c7",
  装备选购: "#7c3aed",
  计划: "#e11d48",
  其他: "#64748b",
};

const OVERVIEW_THRESHOLD = 200;

function GraphNode({ data }: NodeProps) {
  const { title, degree, stale, uncited, color } = data;
  return (
    <div
      className={cn(
        "max-w-[180px] rounded-lg border bg-white px-3 py-2 shadow-sm",
        stale ? "border-amber-400" : "border-slate-200"
      )}
      style={{ borderTop: `3px solid ${color}` }}
    >
      <p className="truncate text-xs font-semibold text-slate-800">{title}</p>
      <div className="mt-1 flex items-center gap-1.5">
        <span className="text-[10px] text-slate-400">度 {degree}</span>
        {stale && (
          <Badge className="bg-amber-100 px-1 py-0 text-[10px] text-amber-700">
            过期
          </Badge>
        )}
        {uncited && (
          <Badge className="bg-red-50 px-1 py-0 text-[10px] text-red-600">
            未引用
          </Badge>
        )}
      </div>
    </div>
  );
}

const nodeTypes = { graph: GraphNode };

interface KBGraphProps {
  kbId: string;
  graph: KBGraphData;
  onRequestMode: (mode: "full" | "overview") => Promise<void>;
}

export function KBGraph({ kbId, graph, onRequestMode }: KBGraphProps) {
  const total = graph.stats.total_nodes as number | undefined;
  const [mode, setMode] = useState<"full" | "overview">(
    (graph.stats.mode as "full" | "overview") || "full"
  );
  const [selected, setSelected] = useState<string | null>(null);
  const [refs, setRefs] = useState<KBDocumentReferences | null>(null);
  const [refLoading, setRefLoading] = useState(false);

  const canDownsample = (total ?? graph.nodes.length) >= OVERVIEW_THRESHOLD;

  const nodes: Node[] = useMemo(
    () =>
      graph.nodes.map((n, i) => {
        const color = GROUP_COLORS[n.semantic_group ?? "其他"] ?? "#64748b";
        return {
          id: n.id,
          type: "graph",
          data: {
            title: n.title,
            degree: n.degree ?? 0,
            stale: Boolean(n.stale_since),
            uncited: Boolean(n.uncited),
            color,
          },
          position: circularPosition(i, graph.nodes.length),
        };
      }),
    [graph.nodes]
  );

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e, i) => ({
        id: `${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        type: "default",
        markerEnd: { type: MarkerType.ArrowClosed },
        style: {
          stroke: e.type === "cites" ? "#94a3b8" : "#cbd5e1",
          strokeDasharray: e.type === "links_to" ? "4 3" : undefined,
        },
      })),
    [graph.edges]
  );

  const loadRefs = useCallback(
    async (docId: string) => {
      setSelected(docId);
      setRefLoading(true);
      try {
        setRefs(await kbApi.getReferences(kbId, docId));
      } catch {
        setRefs(null);
      } finally {
        setRefLoading(false);
      }
    },
    [kbId]
  );

  const toggleMode = async (next: "full" | "overview") => {
    setMode(next);
    setRefs(null);
    await onRequestMode(next);
  };

  return (
    <div className="relative h-[520px] w-full overflow-hidden rounded-xl border border-emerald-100 bg-white/70">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.2}
        onNodeClick={(_, n) => void loadRefs(n.id)}
      >
        <Background bgColor="#f0fdf4" gap={16} />
        <Controls />
      </ReactFlow>

      {/* 概览/全量切换 */}
      {canDownsample && (
        <div className="absolute left-3 top-3 z-10 flex gap-1 rounded-lg border border-emerald-100 bg-white p-1 shadow-sm">
          {(["overview", "full"] as const).map((m) => (
            <button
              key={m}
              onClick={() => void toggleMode(m)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs",
                mode === m
                  ? "bg-emerald-600 text-white"
                  : "text-slate-600 hover:bg-emerald-50"
              )}
            >
              {m === "overview" ? "概览" : "全量"}
            </button>
          ))}
        </div>
      )}

      {/* 图例 */}
      <div className="absolute right-3 top-3 z-10 flex max-w-[180px] flex-wrap gap-1.5 rounded-lg border border-emerald-100 bg-white p-2 shadow-sm">
        {Object.entries(GROUP_COLORS).map(([g, c]) => (
          <span key={g} className="flex items-center gap-1 text-[10px] text-slate-600">
            <span className="inline-block size-2 rounded-full" style={{ background: c }} />
            {g}
          </span>
        ))}
      </div>

      {/* 节点详情面板 */}
      {selected && (
        <div className="absolute right-3 top-[88px] z-10 w-64 rounded-xl border border-emerald-100 bg-white p-3 shadow-lg">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold text-slate-800">引用关系</p>
            <button
              onClick={() => setSelected(null)}
              className="text-xs text-slate-400 hover:text-slate-600"
            >
              关闭
            </button>
          </div>
          {refLoading ? (
            <div className="flex items-center justify-center py-4 text-emerald-500">
              <Loader2 className="size-4 animate-spin" />
            </div>
          ) : refs ? (
            <div className="space-y-3 text-xs text-slate-600">
              <div>
                <p className="mb-1 font-medium">引用了谁（出边）</p>
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
                <p className="mb-1 font-medium">被谁引用（入边）</p>
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
          ) : (
            <p className="text-slate-400">加载引用失败</p>
          )}
        </div>
      )}
    </div>
  );
}

function circularPosition(index: number, count: number): { x: number; y: number } {
  if (count <= 1) return { x: 0, y: 0 };
  const radius = Math.max(120, count * 9);
  const angle = (2 * Math.PI * index) / count;
  return {
    x: radius * Math.cos(angle),
    y: radius * Math.sin(angle),
  };
}