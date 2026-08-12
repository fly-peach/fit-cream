import { useCallback, useMemo, useRef, useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Loader2 } from "lucide-react";
import {
  kbApi,
  type KBGraphData,
  type KBGraphEdge,
  type KBGraphNode,
  type KBDocumentReferences,
} from "@/lib/kb-api";

type NodeLayer = "center" | "inner" | "middle" | "outer";

interface RadialNodeData {
  id: string;
  x: number;
  y: number;
  radius: number;
  color: string;
  layer: NodeLayer;
  degree: number;
  title: string;
  stale: boolean;
  uncited: boolean;
}

interface LayoutResult {
  positions: Map<string, { x: number; y: number }>;
  nodeData: Map<string, RadialNodeData>;
  rings: number[];
}

const LAYER_CONFIG: Record<NodeLayer, { radius: number; size: number; color: string }> = {
  center: { radius: 0, size: 24, color: "#ea580c" },
  inner: { radius: 120, size: 16, color: "#f97316" },
  middle: { radius: 240, size: 12, color: "#fb923c" },
  outer: { radius: 360, size: 8, color: "#94a3b8" },
};

function computeRadialLayout(
  nodes: KBGraphNode[],
  edges: KBGraphEdge[]
): LayoutResult {
  if (nodes.length === 0) {
    return { positions: new Map(), nodeData: new Map(), rings: [] };
  }

  const degree = new Map<string, number>();
  for (const n of nodes) degree.set(n.id, n.degree ?? 0);
  for (const e of edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }

  const sorted = [...nodes].sort(
    (a, b) => (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0)
  );

  const n = sorted.length;
  const centerCount = 1;
  const innerEnd = Math.max(centerCount, Math.ceil(n * 0.1));
  const middleEnd = Math.max(innerEnd, Math.ceil(n * 0.4));

  const layers = new Map<string, NodeLayer>();
  sorted.forEach((node, i) => {
    if (i < centerCount) layers.set(node.id, "center");
    else if (i < innerEnd) layers.set(node.id, "inner");
    else if (i < middleEnd) layers.set(node.id, "middle");
    else layers.set(node.id, "outer");
  });

  const layerNodes: Record<NodeLayer, KBGraphNode[]> = {
    center: [],
    inner: [],
    middle: [],
    outer: [],
  };
  for (const node of sorted) {
    layerNodes[layers.get(node.id)!].push(node);
  }

  const positions = new Map<string, { x: number; y: number }>();
  const nodeData = new Map<string, RadialNodeData>();

  for (const [layer, layerNodesList] of Object.entries(layerNodes) as [NodeLayer, KBGraphNode[]][]) {
    const config = LAYER_CONFIG[layer];
    const count = layerNodesList.length;

    layerNodesList.forEach((node, i) => {
      const x = layer === "center" ? 0 : config.radius * Math.cos((i / count) * Math.PI * 2 - Math.PI / 2);
      const y = layer === "center" ? 0 : config.radius * Math.sin((i / count) * Math.PI * 2 - Math.PI / 2);

      positions.set(node.id, { x, y });
      nodeData.set(node.id, {
        id: node.id,
        x,
        y,
        radius: config.size,
        color: config.color,
        layer,
        degree: degree.get(node.id) ?? 0,
        title: node.title,
        stale: Boolean(node.stale_since),
        uncited: Boolean(node.uncited),
      });
    });
  }

  const rings = [120, 240, 360];

  return { positions, nodeData, rings };
}

function truncateTitle(title: string, maxLen = 12): string {
  return title.length > maxLen ? title.slice(0, maxLen) + "…" : title;
}

interface KBGraphProps {
  kbId: string;
  graph: KBGraphData;
  onRequestMode: (mode: "full" | "overview") => Promise<void>;
}

export function KBGraph({ kbId, graph }: KBGraphProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const [refs, setRefs] = useState<KBDocumentReferences | null>(null);
  const [refLoading, setRefLoading] = useState(false);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<number | null>(null);
  const [tooltipPos, setTooltipPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const svgRef = useRef<SVGSVGElement>(null);
  const [viewBox, setViewBox] = useState({ width: 900, height: 700 });

  useEffect(() => {
    const updateSize = () => {
      if (svgRef.current) {
        const rect = svgRef.current.parentElement?.getBoundingClientRect();
        if (rect) {
          setViewBox({ width: rect.width, height: rect.height });
        }
      }
    };
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  const layout = useMemo(
    () => computeRadialLayout(graph.nodes, graph.edges),
    [graph.nodes, graph.edges]
  );

  const connectedEdgeIds = useMemo(() => {
    if (!selected) return null;
    const set = new Set<number>();
    graph.edges.forEach((e, i) => {
      if (e.source === selected || e.target === selected) set.add(i);
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

  const cx = viewBox.width / 2;
  const cy = viewBox.height / 2;

  const handleNodeMouseEnter = (nodeId: string, e: React.MouseEvent) => {
    setHoveredNode(nodeId);
    const svgRect = svgRef.current?.getBoundingClientRect();
    if (svgRect) {
      setTooltipPos({ x: e.clientX - svgRect.left, y: e.clientY - svgRect.top });
    }
  };

  const handleEdgeMouseEnter = (edgeIdx: number, e: React.MouseEvent) => {
    setHoveredEdge(edgeIdx);
    const svgRect = svgRef.current?.getBoundingClientRect();
    if (svgRect) {
      setTooltipPos({ x: e.clientX - svgRect.left, y: e.clientY - svgRect.top });
    }
  };

  const hoveredNodeData = hoveredNode ? layout.nodeData.get(hoveredNode) : null;
  const hoveredEdgeData = hoveredEdge !== null ? graph.edges[hoveredEdge] : null;

  return (
    <div className="relative h-[72vh] min-h-[600px] w-full overflow-hidden rounded-xl border border-slate-200" style={{ background: "#fafafa" }}>
      <svg
        ref={svgRef}
        width="100%"
        height="100%"
        viewBox={`0 0 ${viewBox.width} ${viewBox.height}`}
        className="absolute inset-0"
      >
        <g transform={`translate(${cx}, ${cy})`}>
          {layout.rings.map((r) => (
            <circle
              key={r}
              cx={0}
              cy={0}
              r={r}
              fill="none"
              stroke="#e2e8f0"
              strokeWidth={1}
              strokeDasharray="4 4"
            />
          ))}

          {graph.edges.map((e, i) => {
            const sourcePos = layout.positions.get(e.source);
            const targetPos = layout.positions.get(e.target);
            if (!sourcePos || !targetPos) return null;

            const highlighted = connectedEdgeIds?.has(i) ?? false;
            const dimmed = connectedEdgeIds ? !highlighted : false;
            const isHovered = hoveredEdge === i;

            return (
              <line
                key={i}
                x1={sourcePos.x}
                y1={sourcePos.y}
                x2={targetPos.x}
                y2={targetPos.y}
                stroke={highlighted ? "#059669" : "#cbd5e1"}
                strokeWidth={highlighted ? 2 : 1}
                opacity={dimmed ? 0.15 : isHovered ? 1 : 0.4}
                onMouseEnter={(ev) => handleEdgeMouseEnter(i, ev)}
                onMouseLeave={() => setHoveredEdge(null)}
                className="cursor-pointer"
                style={{ transition: "opacity 120ms, stroke 120ms" }}
              />
            );
          })}

          {graph.nodes.map((n) => {
            const data = layout.nodeData.get(n.id);
            if (!data) return null;

            const isSelected = n.id === selected;
            const dimmed = connectedNodeIds ? !connectedNodeIds.has(n.id) : false;
            const isHovered = hoveredNode === n.id;

            return (
              <g
                key={n.id}
                transform={`translate(${data.x}, ${data.y})`}
                opacity={dimmed ? 0.15 : 1}
                style={{ transition: "opacity 120ms" }}
                onMouseEnter={(e) => handleNodeMouseEnter(n.id, e)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => void loadRefs(n.id)}
                className="cursor-pointer"
              >
                {isSelected && (
                  <circle
                    cx={0}
                    cy={0}
                    r={data.radius + 4}
                    fill="none"
                    stroke="#ea580c"
                    strokeWidth={2}
                    opacity={0.6}
                  />
                )}
                <circle
                  cx={0}
                  cy={0}
                  r={data.radius}
                  fill={data.color}
                  stroke={isHovered ? "#fff" : "none"}
                  strokeWidth={isHovered ? 2 : 0}
                  style={{
                    filter: isSelected ? "drop-shadow(0 0 6px #ea580c)" : undefined,
                    transition: "stroke 120ms",
                  }}
                />
                <text
                  y={data.radius + 14}
                  textAnchor="middle"
                  className="select-none fill-slate-500 text-[10px]"
                >
                  {truncateTitle(data.title)}
                </text>
              </g>
            );
          })}
        </g>
      </svg>

      {hoveredNodeData && (
        <div
          className="pointer-events-none absolute z-20 whitespace-nowrap rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-xs shadow-md"
          style={{
            left: tooltipPos.x + 12,
            top: tooltipPos.y - 10,
          }}
        >
          <p className="font-semibold text-slate-800">{hoveredNodeData.title}</p>
          <p className="text-slate-500">
            度 {hoveredNodeData.degree} · {hoveredNodeData.layer === "center" ? "中心" : hoveredNodeData.layer === "inner" ? "内圈" : hoveredNodeData.layer === "middle" ? "中圈" : "外圈"}
          </p>
        </div>
      )}

      {hoveredEdgeData && (
        <div
          className="pointer-events-none absolute z-20 whitespace-nowrap rounded-md border border-emerald-200 bg-white px-2 py-1 text-[10px] font-medium text-emerald-700 shadow-sm"
          style={{
            left: tooltipPos.x + 12,
            top: tooltipPos.y - 10,
          }}
        >
          {hoveredEdgeData.type === "cites"
            ? `引用${hoveredEdgeData.page ? ` p.${hoveredEdgeData.page}` : ""}`
            : "链接"}
        </div>
      )}

      {selected && (
        <div className="absolute right-3 top-3 z-10 w-64 rounded-xl border border-slate-200 bg-white p-3 shadow-lg">
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
