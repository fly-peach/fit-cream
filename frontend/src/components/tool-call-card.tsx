import { useEffect, useMemo, useRef, useState } from "react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";
import type { ToolCall } from "@/types/chat";
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  CodeIcon,
  ExternalLinkIcon,
  Loader2Icon,
  WrenchIcon,
  XCircleIcon,
} from "lucide-react";

/** 工具名 -> 中文展示名 / 图标映射（与 chat.tsx 步骤节点共用，独立模块避免 react-refresh 告警） */
import { toolIconMap, toolNameMap } from "@/components/tool-meta";

/** 图标底色（emerald 系内做细微变化，保持整体调性一致） */
const iconTintMap: Record<string, string> = {
  checkin_tool: "from-emerald-500 to-teal-600",
  create_checkin_tool: "from-emerald-500 to-teal-600",
  get_streak_tool: "from-orange-400 to-amber-500",
  query_checkins_tool: "from-emerald-500 to-teal-600",
  query_stats_tool: "from-teal-500 to-cyan-600",
  create_diet_plan_tool: "from-lime-500 to-emerald-600",
  record_meal_tool: "from-lime-500 to-emerald-600",
  query_diet_summary_tool: "from-lime-500 to-emerald-600",
  manage_meal_tool: "from-lime-500 to-emerald-600",
  set_nutrition_goals_tool: "from-lime-500 to-emerald-600",
  get_exercises_tool: "from-emerald-500 to-teal-600",
  search_knowledge_base: "from-teal-500 to-cyan-600",
  read_kb_document: "from-teal-500 to-cyan-600",
  recall_memory: "from-emerald-500 to-teal-600",
  save_preference: "from-emerald-400 to-teal-500",
  save_user_fact: "from-emerald-400 to-teal-500",
  list_user_profile: "from-emerald-400 to-teal-500",
  save_event: "from-emerald-400 to-teal-500",
  skill_load_tool: "from-teal-500 to-cyan-600",
  get_user_summary_tool: "from-emerald-400 to-teal-500",
};

/** 常见输出字段的中文标签 */
const keyLabelMap: Record<string, string> = {
  current_streak: "当前连续",
  longest_streak: "最长连续",
  last_checkin_date: "上次打卡",
  date: "日期",
  checkin_date: "打卡日期",
  exercises_count: "动作数",
  duration_min: "时长(分钟)",
  calories_burned: "消耗(kcal)",
  period: "周期",
  total: "共计",
  analysis: "分析",
  stats: "统计数据",
  total_workouts: "训练次数",
  total_duration_min: "总时长(分钟)",
  average_mood: "平均心情",
  current_weight_kg: "当前体重(kg)",
  height_cm: "身高(cm)",
  weight_kg: "体重(kg)",
  age: "年龄",
  gender: "性别",
  goal: "目标",
  name: "名称",
  difficulty: "难度",
  weeks: "周数",
  days_per_week: "每周天数",
  status: "状态",
  created_at: "创建时间",
  calories: "热量(kcal)",
  protein_g: "蛋白质(g)",
  carbs_g: "碳水(g)",
  fat_g: "脂肪(g)",
  portion: "份量",
  meal_type: "餐次",
  meal_date: "日期",
  food_name: "食物",
  intake: "今日摄入",
  goals: "营养目标",
  goal_met: "达标情况",
  profile: "档案",
  plans: "计划列表",
  results: "检索结果",
  document: "文档",
  title: "标题",
  filename: "文件名",
  content: "内容",
  tags: "标签",
  sets_done: "组数",
  reps_done: "次数",
  rpe: "RPE",
  mood: "心情",
  note: "备注",
  notes: "备注",
  query: "关键词",
  total_calories: "总热量(kcal)",
  total_protein_g: "总蛋白(g)",
  total_carbs_g: "总碳水(g)",
  total_fat_g: "总脂肪(g)",
};

/** 枚举值 -> 中文 */
const enumValueMap: Record<string, Record<string, string>> = {
  goal: {
    lose_fat: "减脂",
    gain_muscle: "增肌",
    maintain: "保持健康",
    improve_health: "体能提升",
  },
  difficulty: { beginner: "初级", intermediate: "中级", advanced: "高级" },
  gender: { male: "男", female: "女", other: "其他" },
  meal_type: { breakfast: "早餐", lunch: "午餐", dinner: "晚餐", snack: "加餐" },
  period: { weekly: "本周", monthly: "本月", all: "全部", body: "体重" },
  status: { active: "进行中", paused: "已暂停", completed: "已完成", archived: "已归档" },
  actual_intensity: { low: "低", medium: "中", high: "高" },
};

/** 这些字段不进卡片正文：success/error 走状态徽标与错误条，message 走摘要行 */
const SKIP_KEYS = new Set(["success", "error_code", "message", "error"]);
/** 站内详情页链接字段：从普通字段中剔除，单独渲染为可点击链接 */
const LINK_KEYS = new Set(["url"]);
const isIdKey = (k: string) => k === "id" || k.endsWith("_id");

function labelFor(key: string): string {
  return keyLabelMap[key] ?? key;
}

function formatScalar(value: unknown, key?: string): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (key && enumValueMap[key] && typeof value === "string") {
    return enumValueMap[key][value] ?? value;
  }
  return String(value);
}

/** 解析工具输出：可能是 JSON 字符串、普通文本或对象 */
function parseOutput(output: unknown): {
  obj: Record<string, unknown> | null;
  text: string | null;
} {
  if (output === null || output === undefined) return { obj: null, text: null };
  if (typeof output === "string") {
    const s = output.trim();
    if (!s) return { obj: null, text: null };
    if (s.startsWith("{") || s.startsWith("[")) {
      try {
        const parsed = JSON.parse(s) as unknown;
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          return { obj: parsed as Record<string, unknown>, text: null };
        }
      } catch {
        // 非 JSON，按纯文本处理
      }
    }
    return { obj: null, text: s };
  }
  if (typeof output === "object") {
    if (Array.isArray(output)) return { obj: null, text: JSON.stringify(output) };
    return { obj: output as Record<string, unknown>, text: null };
  }
  return { obj: null, text: String(output) };
}

/** 估算内容体量，决定是否默认折叠 */
function isLargeContent(
  obj: Record<string, unknown> | null,
  text: string | null
): boolean {
  if (text) return text.length > 160;
  if (!obj) return false;
  let score = 0;
  for (const [k, v] of Object.entries(obj)) {
    if (SKIP_KEYS.has(k) || isIdKey(k)) continue;
    if (Array.isArray(v)) score += v.length * 2;
    else if (v && typeof v === "object") score += 2;
    else if (typeof v === "string" && v.length > 60) score += 2;
    else score += 1;
  }
  return score >= 6;
}

/** 卡片头部的一句话摘要 */
function getSummary(
  tc: ToolCall,
  obj: Record<string, unknown> | null,
  text: string | null
): string {
  if (tc.status === "running") return "正在执行…";
  if (tc.status === "error") return tc.error || "执行出错";
  if (obj) {
    if (obj.success === false) return String(obj.error || "执行失败");
    if (typeof obj.message === "string" && obj.message) return obj.message;
  }
  if (text) return text.length > 60 ? `${text.slice(0, 60)}…` : text;
  return "已完成";
}

function ScalarChip({ label, value, k }: { label: string; value: unknown; k?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 rounded-md bg-white/80 px-2 py-1 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.08)]">
      <span className="shrink-0 text-[11px] text-emerald-700/55">{label}</span>
      <span className="truncate text-right text-xs font-medium text-emerald-950">
        {formatScalar(value, k)}
      </span>
    </div>
  );
}

function TextBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="space-y-1">
      <p className="text-[11px] font-medium text-emerald-700/55">{label}</p>
      <p className="max-h-36 overflow-y-auto whitespace-pre-wrap rounded-md bg-white/80 px-2.5 py-1.5 text-xs leading-relaxed text-emerald-950/85 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.08)]">
        {value}
      </p>
    </div>
  );
}

/** 站内详情页链接（按钮样式，用于单对象区域顶部，如 read_kb_document 的 document） */
function DetailLink({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-emerald-200/60 transition-colors hover:bg-emerald-100 hover:text-emerald-800"
    >
      <ExternalLinkIcon className="size-3.5" />
      查看详情
    </a>
  );
}

/** 紧凑链接（用于数组项标题行右侧，如 exercise / kb search 列表项） */
function DetailLinkInline({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex shrink-0 items-center gap-0.5 text-[11px] font-medium text-emerald-600 transition-colors hover:text-emerald-800 hover:underline"
    >
      详情
      <ExternalLinkIcon className="size-3" />
    </a>
  );
}

function ReadableFields({
  data,
  depth = 0,
}: {
  data: Record<string, unknown>;
  depth?: number;
}) {
  const url = typeof data.url === "string" ? data.url : null;
  const entries = Object.entries(data).filter(
    ([k, v]) =>
      !SKIP_KEYS.has(k) && !LINK_KEYS.has(k) && !isIdKey(k) && v !== null && v !== undefined && v !== ""
  );
  if (!entries.length && !url) return null;

  const shortScalars = entries.filter(
    ([, v]) => typeof v !== "object" && String(v).length <= 40
  );
  const longTexts = entries.filter(
    ([, v]) => typeof v === "string" && v.length > 40
  );
  const objects = entries.filter(
    ([, v]) => v && typeof v === "object" && !Array.isArray(v)
  );
  const arrays = entries.filter(([, v]) => Array.isArray(v));

  return (
    <div className="space-y-2.5">
      {url && <DetailLink url={url} />}
      {shortScalars.length > 0 && (
        <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
          {shortScalars.map(([k, v]) => (
            <ScalarChip key={k} label={labelFor(k)} value={v} k={k} />
          ))}
        </div>
      )}
      {longTexts.map(([k, v]) => (
        <TextBlock key={k} label={labelFor(k)} value={String(v)} />
      ))}
      {objects.map(([k, v]) => (
        <ObjectSection
          key={k}
          label={labelFor(k)}
          data={v as Record<string, unknown>}
          depth={depth + 1}
        />
      ))}
      {arrays.map(([k, v]) => (
        <ArraySection key={k} label={labelFor(k)} items={v as unknown[]} depth={depth + 1} />
      ))}
    </div>
  );
}

function ObjectSection({
  label,
  data,
  depth,
}: {
  label: string;
  data: Record<string, unknown>;
  depth: number;
}) {
  if (depth > 2) {
    return <TextBlock label={label} value={JSON.stringify(data, null, 2)} />;
  }
  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-medium text-emerald-700/55">{label}</p>
      <div className="rounded-lg bg-emerald-50/60 px-2 py-1.5">
        <ReadableFields data={data} depth={depth} />
      </div>
    </div>
  );
}

function ArraySection({
  label,
  items,
  depth,
}: {
  label: string;
  items: unknown[];
  depth: number;
}) {
  if (!items.length) return null;
  const allScalar = items.every((i) => typeof i !== "object" || i === null);
  if (allScalar) {
    return (
      <div className="space-y-1">
        <p className="text-[11px] font-medium text-emerald-700/55">{label}</p>
        <div className="flex flex-wrap gap-1">
          {items.map((it, i) => (
            <span
              key={i}
              className="rounded-full bg-white/80 px-2 py-0.5 text-[11px] font-medium text-emerald-800 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.15)]"
            >
              {formatScalar(it)}
            </span>
          ))}
        </div>
      </div>
    );
  }
  return (
    <div className="space-y-1.5">
      <p className="text-[11px] font-medium text-emerald-700/55">
        {label}（{items.length}）
      </p>
      <div className="space-y-1.5">
        {items.map((it, i) => (
          <ArrayItemCard key={i} item={it} depth={depth} />
        ))}
      </div>
    </div>
  );
}

function ArrayItemCard({ item, depth }: { item: unknown; depth: number }) {
  if (!item || typeof item !== "object") {
    return <p className="text-xs text-emerald-950/85">{formatScalar(item)}</p>;
  }
  const obj = item as Record<string, unknown>;
  if (depth > 2) {
    return <TextBlock label="" value={JSON.stringify(obj, null, 2)} />;
  }
  const titleKey = ["name", "title", "document_title", "food_name", "exercise_name", "date", "query"].find(
    (k) => obj[k] !== undefined && obj[k] !== null && obj[k] !== ""
  );
  const url = typeof obj.url === "string" ? obj.url : null;
  const rest = { ...obj };
  if (titleKey) delete rest[titleKey];
  if (url) delete rest["url"];
  return (
    <div className="rounded-lg bg-white/80 px-2.5 py-2 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.1)]">
      {(titleKey || url) && (
        <div className="mb-1 flex items-center justify-between gap-2">
          <p className="text-xs font-semibold text-emerald-950">
            {titleKey ? formatScalar(obj[titleKey], titleKey) : ""}
          </p>
          {url && <DetailLinkInline url={url} />}
        </div>
      )}
      <ReadableFields data={rest} depth={depth} />
    </div>
  );
}

/** 原始数据（入参 + 返回）折叠区，默认收起，供需要时排查 */
function RawData({ tc }: { tc: ToolCall }) {
  const [open, setOpen] = useState(false);
  const rawOutput =
    typeof tc.output === "string" ? tc.output : JSON.stringify(tc.output, null, 2);
  return (
    <Collapsible open={open} onOpenChange={setOpen} className="mt-2.5">
      <CollapsibleTrigger className="flex items-center gap-1 text-[11px] font-medium text-emerald-600/50 transition-colors hover:text-emerald-700">
        <CodeIcon className="size-3" />
        原始数据
        <ChevronDownIcon
          className={cn("size-3 transition-transform duration-200", open && "rotate-180")}
        />
      </CollapsibleTrigger>
      {open && (
        <CollapsibleContent className="mt-1.5 space-y-2">
          <div className="space-y-1">
            <p className="text-[10px] font-medium uppercase tracking-wide text-emerald-700/45">
              入参
            </p>
            <pre className="max-h-32 overflow-auto rounded-md bg-emerald-950/[0.04] px-2.5 py-1.5 text-[10px] leading-relaxed text-emerald-900/60">
              {JSON.stringify(tc.input, null, 2)}
            </pre>
          </div>
          <div className="space-y-1">
            <p className="text-[10px] font-medium uppercase tracking-wide text-emerald-700/45">
              返回
            </p>
            <pre className="max-h-32 overflow-auto rounded-md bg-emerald-950/[0.04] px-2.5 py-1.5 text-[10px] leading-relaxed text-emerald-900/60">
              {rawOutput || "（无）"}
            </pre>
          </div>
        </CollapsibleContent>
      )}
    </Collapsible>
  );
}

/**
 * 工具调用卡片：把一次 Tool 调用封装为可读卡片。
 *
 * - 头部：图标 + 中文名 + 状态徽标 + 一句话摘要，始终可见
 * - 正文：结构化、中文化的结果渲染（键值对 / 分组 / 列表），不直接暴露字典
 * - 内容较多时默认折叠为 expander，点开头部展开
 * - 原始入参 / 返回字典收进「原始数据」二级折叠，默认隐藏
 *
 * embedded 模式：嵌入 ChainOfThought 步骤节点时使用，仅渲染结果正文
 *（无卡片外壳与头部，节点标题/图标/状态由外层步骤承载，避免重复）。
 */
export function ToolCallCard({ tc, embedded = false }: { tc: ToolCall; embedded?: boolean }) {
  const { obj, text } = useMemo(() => parseOutput(tc.output), [tc.output]);

  const running = tc.status === "running";
  const failed = tc.status === "error" || obj?.success === false;
  const hasBody = !running && (!!obj || !!text);
  const large = isLargeContent(obj, text);

  // 内容少则直接展开，内容多则折叠为 expander；出错时展开以便查看原因。
  // 流式场景下卡片先以 running 挂载（无正文），结果到达后 hasBody 才变 true，
  // 因此需要在 false→true 的跃迁上按体量决定展开与否，而不是只靠初始值。
  const [open, setOpen] = useState(() => hasBody && (!large || failed));
  const prevHasBody = useRef(hasBody);
  useEffect(() => {
    if (hasBody && !prevHasBody.current) {
      setOpen(!large || failed);
    }
    prevHasBody.current = hasBody;
  }, [hasBody, large, failed]);

  const Icon = toolIconMap[tc.name] ?? WrenchIcon;
  const title = toolNameMap[tc.name] ?? tc.name;
  const tint = iconTintMap[tc.name] ?? "from-emerald-500 to-teal-600";
  const summary = getSummary(tc, obj, text);
  const errorMsg = failed
    ? tc.error || (obj && String(obj.error || "")) || "执行失败"
    : "";

  if (embedded) {
    if (!hasBody) return null;
    return (
      <div className="not-prose w-full space-y-2">
        {failed && errorMsg && (
          <div className="flex items-start gap-2 rounded-md bg-red-50 px-2.5 py-2 text-xs leading-relaxed text-red-700 ring-1 ring-red-200/60">
            <XCircleIcon className="mt-0.5 size-3.5 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
        {large && !failed ? (
          <Collapsible open={open} onOpenChange={setOpen}>
            <CollapsibleTrigger className="flex items-center gap-1 text-xs font-medium text-emerald-600/70 transition-colors hover:text-emerald-700">
              {open ? "收起详情" : "查看详情"}
              <ChevronDownIcon
                className={cn("size-3 transition-transform duration-200", open && "rotate-180")}
              />
            </CollapsibleTrigger>
            {open && (
              <CollapsibleContent className="pt-1.5">
                {obj && <ReadableFields data={obj} />}
                {text && <TextBlock label="结果" value={text} />}
              </CollapsibleContent>
            )}
          </Collapsible>
        ) : (
          <>
            {obj && <ReadableFields data={obj} />}
            {text && <TextBlock label="结果" value={text} />}
          </>
        )}
        <RawData tc={tc} />
      </div>
    );
  }

  const header = (
    <div className="flex w-full items-center gap-3 px-3 py-2.5 text-left">
      <span
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm",
          tint,
          running && "animate-pulse"
        )}
      >
        <Icon className="size-4" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-2">
          <span className="truncate text-sm font-semibold text-emerald-950">{title}</span>
          {running ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 ring-1 ring-amber-200/70">
              <Loader2Icon className="size-3 animate-spin" />
              执行中
            </span>
          ) : failed ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-medium text-red-700 ring-1 ring-red-200/70">
              <XCircleIcon className="size-3" />
              失败
            </span>
          ) : (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700 ring-1 ring-emerald-200/70">
              <CheckCircle2Icon className="size-3" />
              完成
            </span>
          )}
        </span>
        <span
          className={cn(
            "truncate text-xs",
            failed ? "text-red-600/80" : "text-emerald-700/60"
          )}
        >
          {summary}
        </span>
      </span>
      {hasBody && (
        <ChevronDownIcon
          className={cn(
            "size-4 shrink-0 text-emerald-600/50 transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      )}
    </div>
  );

  return (
    <div
      className={cn(
        "not-prose w-full overflow-hidden rounded-xl border bg-white/80 shadow-sm shadow-emerald-900/[0.04] transition-shadow",
        failed
          ? "border-red-200/80 border-l-2 border-l-red-400"
          : running
            ? "border-amber-200/70 border-l-2 border-l-amber-400"
            : "border-emerald-100 border-l-2 border-l-emerald-400 hover:shadow-md hover:shadow-emerald-900/[0.06]"
      )}
    >
      {hasBody ? (
        <Collapsible open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger className="block w-full transition-colors hover:bg-emerald-50/50">
            {header}
          </CollapsibleTrigger>
          {open && (
            <CollapsibleContent>
              <div className="border-t border-emerald-100/70 bg-emerald-50/40 px-3 py-3">
                {failed && errorMsg && (
                  <div className="mb-2 flex items-start gap-2 rounded-md bg-red-50 px-2.5 py-2 text-xs leading-relaxed text-red-700 ring-1 ring-red-200/60">
                    <XCircleIcon className="mt-0.5 size-3.5 shrink-0" />
                    <span>{errorMsg}</span>
                  </div>
                )}
                {obj && <ReadableFields data={obj} />}
                {text && <TextBlock label="结果" value={text} />}
                <RawData tc={tc} />
              </div>
            </CollapsibleContent>
          )}
        </Collapsible>
      ) : (
        header
      )}
    </div>
  );
}
