import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceSimulation,
} from "d3-force";
import {
  Background,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  kbApi,
  type KBGraphData,
  type KBGraphEdge,
  type KBDocumentReferences,
} from "@/lib/kb-api";

const OVERVIEW_THRESHOLD = 200;

// 节点大小映射（按度数）
function getNodeRadius(degree: number): number {
  if (degree >= 10) return 8;
  if (degree >= 5) return 6;
  if (degree >= 3) return 5;
  return 4;
}

// 节点颜色：高度数白色，其他灰色，特定语义组绿色
function getNodeColor(degree: number, semanticGroup: string): string {
  if (degree >= 8) return "#ffffff";
  if (semanticGroup === "训练动作" || semanticGroup === "饮食营养") return "#10b981";
  return "#6b7280";
}

function GraphNode({ data }: NodeProps) {
  const { title, degree, semanticGroup } = data;
  const radius = getNodeRadius(degree);
  const color = getNodeColor(degree, semanticGroup);

  return (
    <div className="group relative flex items-center justify-center">
      <div
        className="rounded-full transition-all duration-200 group-hover:scale-125"
        style={{
          width: radius * 2,
          height: radius * 2,
          background: color,
          boxShadow: degree >= 8 ? `0 0 12px ${color}40` : undefined,
        }}
      />
      {/* 悬停显示标题 */}
      <div className="pointer-events-none absolute -top-8 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-black/80 px-2 py-1 text-xs text-white opacity-0 transition-opacity group-hover:opacity-100">
        {title}
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

  const positions = useMemo(
    () => computeForceLayout(graph.nodes.map((n) => n.id), graph.edges),
    [graph.nodes, graph.edges]
  );

  const nodes: Node[] = useMemo(
    () =>
      graph.nodes.map((n) => ({
        id: n.id,
        type: "graph",
        data: {
          title: n.title,
          degree: n.degree ?? 0,
          semanticGroup: n.semantic_group ?? "其他",
        },
        position: positions.get(n.id) ?? { x: 0, y: 0 },
      })),
    [graph.nodes, positions]
  );

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e, i) => ({
        id: `${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        type: "default",
        style: {
          stroke: "#374151",
          strokeWidth: 1,
          opacity: 0.6,
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
    <div className="relative h-[520px] w-full overflow-hidden rounded-xl bg-[#0a0a0a]">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        minZoom={0.2}
        maxZoom={4}
        onNodeClick={(_, n) => void loadRefs(n.id)}
        proOptions={{ hideAttribution: true }}
      >
        <Background color="#1f2937" gap={20} />
      </ReactFlow>

      {/* 概览/全量切换 */}
      {canDownsample && (
        <div className="absolute left-3 top-3 z-10 flex gap-1 rounded-lg border border-gray-800 bg-black/60 p-1 backdrop-blur">
          {(["overview", "full"] as const).map((m) => (
            <button
              key={m}
              onClick={() => void toggleMode(m)}
              className={cn(
                "rounded-md px-2.5 py-1 text-xs transition-colors",
                mode === m
                  ? "bg-emerald-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
              )}
            >
              {m === "overview" ? "概览" : "全量"}
            </button>
          ))}
        </div>
      )}

      {/* 节点详情面板 */}
      {selected && (
        <div className="absolute right-3 top-3 z-10 w-64 rounded-xl border border-gray-800 bg-black/90 p-3 shadow-lg backdrop-blur">
          <div className="mb-2 flex items-center justify-between">
            <p className="text-xs font-semibold text-gray-200">引用关系</p>
            <button
              onClick={() => setSelected(null)}
              className="text-xs text-gray-500 hover:text-gray-300"
            >
              关闭
            </button>
          </div>
          {refLoading ? (
            <div className="flex items-center justify-center py-4 text-emerald-500">
              <Loader2 className="size-4 animate-spin" />
            </div>
          ) : refs ? (
            <div className="space-y-3 text-xs text-gray-400">
              <div>
                <p className="mb-1 font-medium text-gray-300">引用了谁（出边）</p>
                <ul className="space-y-1">
                  {refs.cites.length === 0 && refs.links_to.length === 0 ? (
                    <li className="text-gray-600">无</li>
                  ) : (
                    [...refs.cites, ...refs.links_to].map((r) => (
                      <li key={r.id}>
                        <Link
                          to={`/knowledge-bases/${kbId}/documents/${r.document_id}`}
                          className="text-emerald-400 hover:underline"
                        >
                          {r.title}
                        </Link>
                      </li>
                    ))
                  )}
                </ul>
              </div>
              <div>
                <p className="mb-1 font-medium text-gray-300">被谁引用（入边）</p>
                <ul className="space-y-1">
                  {refs.cited_by.length === 0 && refs.linked_by.length === 0 ? (
                    <li className="text-gray-600">无</li>
                  ) : (
                    [...refs.cited_by, ...refs.linked_by].map((r) => (
                      <li key={r.id}>
                        <Link
                          to={`/knowledge-bases/${kbId}/documents/${r.document_id}`}
                          className="text-emerald-400 hover:underline"
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
            <p className="text-gray-600">加载引用失败</p>
          )}
        </div>
      )}
    </div>
  );
}

function computeForceLayout(
  nodeIds: string[],
  edges: KBGraphEdge[]
): Map<string, { x: number; y: number }> {
  const nodes = nodeIds.map((id) => ({ id, x: 0, y: 0 }));
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const links = edges.map((e) => ({ source: e.source, target: e.target })) as any[];

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const sim = forceSimulation(nodes as any[])
    .force(
      "link",
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      forceLink<any, any>(links)
        .id((d) => d.id)
        .distance(80)
        .strength(0.4)
    )
    .force("charge", forceManyBody().strength(-300))
    .force("collide", forceCollide(20))
    .force("center", forceCenter(0, 0))
    .stop();

  for (let i = 0; i < 300; i += 1) sim.tick();

  const positions = new Map<string, { x: number; y: number }>();
  for (const n of nodes) positions.set(n.id, { x: n.x, y: n.y });
  return positions;
}