import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  forceCenter,
  forceCollide,
  forceLink,
  forceManyBody,
  forceRadial,
  forceSimulation,
  type SimulationLinkDatum,
  type SimulationNodeDatum,
} from "d3-force";
import {
  Background,
  BaseEdge,
  Controls,
  EdgeLabelRenderer,
  MarkerType,
  ReactFlow,
  getBezierPath,
  type Edge,
  type EdgeProps,
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
  type KBGraphEdge,
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

type HoverEdgeData = {
  type?: string;
  page?: number | null;
  highlighted?: boolean;
  dimmed?: boolean;
};

function HoverEdge({
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  markerEnd,
  data,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });
  const [hovered, setHovered] = useState(false);
  const d = (data ?? {}) as HoverEdgeData;
  const highlighted = d.highlighted ?? false;
  const dimmed = d.dimmed ?? false;
  const edgeType = d.type ?? "cites";
  const stroke = highlighted
    ? "#059669"
    : edgeType === "cites"
      ? "#475569"
      : "#64748b";
  const opacity = dimmed ? 0.12 : 1;
  const labelText =
    edgeType === "cites" ? `引用${d.page ? ` p.${d.page}` : ""}` : "链接";

  return (
    <g
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        interactionWidth={20}
        style={{
          stroke,
          strokeWidth: highlighted ? 3 : 1.8,
          strokeDasharray: edgeType === "links_to" ? "6 4" : undefined,
          opacity,
        }}
      />
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)`,
            pointerEvents: "none",
            opacity: hovered ? 1 : 0,
            transition: "opacity 120ms",
          }}
          className="pointer-events-none whitespace-nowrap rounded border border-emerald-200 bg-white px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 shadow-sm"
        >
          {labelText}
        </div>
      </EdgeLabelRenderer>
    </g>
  );
}

function GraphNode({ data, selected }: NodeProps) {
  const d = data as {
    title?: string;
    degree?: number;
    stale?: boolean;
    uncited?: boolean;
    color?: string;
  };
  const title = d.title ?? "";
  const degree = d.degree ?? 0;
  const color = d.color ?? "#64748b";
  return (
    <div
      className={cn(
        "max-w-[180px] rounded-lg border bg-white px-3 py-2 shadow-sm transition-all",
        d.stale ? "border-amber-400" : "border-slate-200",
        selected && "ring-2 ring-emerald-500"
      )}
      style={{ borderTop: `3px solid ${color}` }}
    >
      <p className="truncate text-xs font-semibold text-slate-800">{title}</p>
      <div className="mt-1 flex items-center gap-1.5">
        <span className="text-[10px] text-slate-400">度 {degree}</span>
        {d.stale && (
          <Badge className="bg-amber-100 px-1 py-0 text-[10px] text-amber-700">
            过期
          </Badge>
        )}
        {d.uncited && (
          <Badge className="bg-red-50 px-1 py-0 text-[10px] text-red-600">
            未引用
          </Badge>
        )}
      </div>
    </div>
  );
}

const nodeTypes = { graph: GraphNode };
const edgeTypes = { hover: HoverEdge };

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

  const connectedEdgeIds = useMemo(() => {
    if (!selected) return null;
    const set = new Set<string>();
    graph.edges.forEach((e, i) => {
      if (e.source === selected || e.target === selected) {
        set.add(`${e.source}-${e.target}-${i}`);
      }
    });
    return set;
  }, [selected, graph.edges]);

  const connectedNodeIds = useMemo(() => {
    if (!selected) return null;
    const set = new Set<string>([selected]);
    graph.edges.forEach((e) => {
      if (e.source === selected) set.add(e.target);
      if (e.target === selected) set.add(e.source);
    });
    return set;
  }, [selected, graph.edges]);

  const nodes: Node[] = useMemo(
    () =>
      graph.nodes.map((n) => {
        const color = GROUP_COLORS[n.semantic_group ?? "其他"] ?? "#64748b";
        const dimmed = connectedNodeIds ? !connectedNodeIds.has(n.id) : false;
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
          position: positions.get(n.id) ?? { x: 0, y: 0 },
          style: { opacity: dimmed ? 0.25 : 1 },
          selected: n.id === selected,
        };
      }),
    [graph.nodes, positions, connectedNodeIds, selected]
  );

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e, i) => {
        const id = `${e.source}-${e.target}-${i}`;
        const highlighted = connectedEdgeIds?.has(id) ?? false;
        const dimmed = connectedEdgeIds ? !highlighted : false;
        const markerColor = highlighted
          ? "#059669"
          : dimmed
            ? "#cbd5e1"
            : e.type === "cites"
              ? "#475569"
              : "#64748b";
        return {
          id,
          source: e.source,
          target: e.target,
          type: "hover",
          animated: highlighted,
          data: {
            type: e.type,
            page: e.page ?? null,
            highlighted,
            dimmed,
          },
          markerEnd: { type: MarkerType.ArrowClosed, color: markerColor },
        };
      }),
    [graph.edges, connectedEdgeIds]
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
    setSelected(null);
    setRefs(null);
    await onRequestMode(next);
  };

  return (
    <div className="relative h-[72vh] min-h-[600px] w-full overflow-hidden rounded-xl border border-emerald-100 bg-white/70">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        elevateEdgesOnSelect
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
              onClick={() => {
                setSelected(null);
                setRefs(null);
              }}
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

interface LayoutNode extends SimulationNodeDatum {
  id: string;
}

function computeForceLayout(
  nodeIds: string[],
  edges: KBGraphEdge[]
): Map<string, { x: number; y: number }> {
  // 度数分圈初始布局 + 力导向微调：高度数节点居中，低度数靠外圈
  const nodes: LayoutNode[] = nodeIds.map((id) => ({ id, x: 0, y: 0 }));
  if (nodes.length === 0) return new Map();

  const degree = new Map<string, number>();
  for (const id of nodeIds) degree.set(id, 0);
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }

  const sorted = [...nodes].sort(
    (a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0)
  );
  const n = sorted.length;
  const maxR = 340;
  const targetRadius = new Map<string, number>();

  sorted.forEach((node, i) => {
    if (i === 0) {
      node.x = 0;
      node.y = 0;
      targetRadius.set(node.id, 0);
    } else {
      const t = n > 1 ? i / (n - 1) : 0;
      const radius = 90 + t * maxR;
      const angle = ((i - 1) / Math.max(1, n - 1)) * Math.PI * 2;
      node.x = radius * Math.cos(angle);
      node.y = radius * Math.sin(angle);
      targetRadius.set(node.id, radius);
    }
  });

  const links: SimulationLinkDatum<LayoutNode>[] = edges.map((e) => ({
    source: e.source,
    target: e.target,
  }));

  const sim = forceSimulation<LayoutNode>(sorted)
    .force(
      "link",
      forceLink<LayoutNode, SimulationLinkDatum<LayoutNode>>(links)
        .id((d) => d.id)
        .distance(130)
        .strength(0.45)
    )
    .force("charge", forceManyBody().strength(-360))
    .force("collide", forceCollide(70))
    .force("center", forceCenter(0, 0))
    .force(
      "radial",
      forceRadial((d) => targetRadius.get(d.id) ?? 100, 0, 0).strength(0.25)
    )
    .stop();

  for (let i = 0; i < 300; i += 1) sim.tick();

  const positions = new Map<string, { x: number; y: number }>();
  for (const node of sorted) positions.set(node.id, { x: node.x ?? 0, y: node.y ?? 0 });
  return positions;
}
