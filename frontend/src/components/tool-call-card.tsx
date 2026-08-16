import { useMemo, useState } from "react";
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
  ClockIcon,
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
  get_streak_tool: "from-orange-400 to-amber-500",
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

/** 常见输出/入参字段的中文标签 */
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
  muscle_group: "肌群",
  equipment: "器械",
  semantic_query: "语义查询",
  target: "目标肌群",
  category: "类别",
  limit: "数量",
  top_k: "数量",
  metric: "指标",
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
  muscle_group: {
    chest: "胸部",
    back: "背部",
    legs: "腿部",
    shoulders: "肩部",
    arms: "手臂",
    core: "核心",
    full_body: "全身",
  },
  equipment: {
    barbell: "杠铃",
    dumbbell: "哑铃",
    machine: "器械",
    bodyweight: "自重",
    cable: "绳索",
    kettlebell: "壶铃",
    band: "弹力带",
  },
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
  if (value === null || value === undefined) return "-";
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

// ===== 统计型查询提取器（从 output 结构化数据生成关键指标）=====

type Metric = { label: string; value: string; ok?: boolean };
type StatsResult = { text?: string; metrics: Metric[]; detailLink?: string };

/** 共享：用户档案（get_profile_summary schema）→ 指标 */
function buildProfileMetrics(profile?: Record<string, unknown> | null): Metric[] {
  const metrics: Metric[] = [];
  if (!profile) return metrics;
  if (profile.name) metrics.push({ label: "昵称", value: String(profile.name) });
  if (profile.gender != null) metrics.push({ label: "性别", value: formatScalar(profile.gender, "gender") });
  if (profile.age != null) metrics.push({ label: "年龄", value: `${profile.age}岁` });
  if (profile.height_cm != null) metrics.push({ label: "身高", value: `${profile.height_cm}cm` });
  if (profile.weight_kg != null) metrics.push({ label: "体重", value: `${profile.weight_kg}kg` });
  if (profile.bmi != null) metrics.push({ label: "BMI", value: String(profile.bmi) });
  if (profile.goal != null) metrics.push({ label: "目标", value: formatScalar(profile.goal, "goal") });
  return metrics;
}

const statsExtractors: Record<string, (obj: Record<string, unknown> | null) => StatsResult> = {
  query_stats_tool: (obj) => {
    const analysis = obj?.analysis as string | undefined;
    const stats = obj?.stats as Record<string, unknown> | undefined;
    const metrics: Metric[] = [];
    if (stats) {
      if (stats.total_workouts != null) metrics.push({ label: "训练次数", value: String(stats.total_workouts) });
      if (stats.total_duration_min != null) metrics.push({ label: "总时长", value: `${stats.total_duration_min}分钟` });
      if (stats.current_streak != null) metrics.push({ label: "连续", value: `${stats.current_streak}天` });
      if (stats.longest_streak != null) metrics.push({ label: "最长连续", value: `${stats.longest_streak}天` });
    }
    return { text: analysis, metrics };
  },
  checkin_tool: (obj) => {
    const metrics: Metric[] = [];
    if (obj?.exercises_count != null) metrics.push({ label: "动作数", value: `${obj.exercises_count}个` });
    if (obj?.duration_min != null) metrics.push({ label: "时长", value: `${obj.duration_min}分钟` });
    if (obj?.current_streak != null) metrics.push({ label: "连续打卡", value: `${obj.current_streak}天` });
    return { metrics };
  },
  get_streak_tool: (obj) => {
    const metrics: Metric[] = [];
    if (obj?.current_streak != null) metrics.push({ label: "当前连续", value: `${obj.current_streak}天` });
    if (obj?.longest_streak != null) metrics.push({ label: "最长连续", value: `${obj.longest_streak}天` });
    if (obj?.last_checkin_date) metrics.push({ label: "上次打卡", value: String(obj.last_checkin_date) });
    return { metrics };
  },
  query_diet_summary_tool: (obj) => {
    const intake = obj?.intake as Record<string, unknown> | undefined;
    const goals = obj?.goals as Record<string, unknown> | undefined;
    const goalMet = obj?.goal_met as Record<string, unknown> | undefined;
    const metrics: Metric[] = [];
    if (intake && goals) {
      const cal = Number(intake.total_calories ?? 0);
      metrics.push({
        label: "热量",
        value: goals.calorie_goal != null ? `${cal}/${goals.calorie_goal} kcal` : `${cal} kcal`,
      });
      const p = Number(intake.total_protein_g ?? 0);
      metrics.push({
        label: "蛋白",
        value: goals.protein_goal_g != null ? `${p}/${goals.protein_goal_g}g` : `${p}g`,
        ok: !!goalMet?.protein,
      });
      const c = Number(intake.total_carbs_g ?? 0);
      metrics.push({
        label: "碳水",
        value: goals.carbs_goal_g != null ? `${c}/${goals.carbs_goal_g}g` : `${c}g`,
        ok: !!goalMet?.carbs,
      });
      const f = Number(intake.total_fat_g ?? 0);
      metrics.push({
        label: "脂肪",
        value: goals.fat_goal_g != null ? `${f}/${goals.fat_goal_g}g` : `${f}g`,
        ok: !!goalMet?.fat,
      });
    }
    return { metrics };
  },
  record_meal_tool: (obj) => {
    const meal = obj?.meal as Record<string, unknown> | undefined;
    const metrics: Metric[] = [];
    if (meal) {
      if (meal.meal_type != null) metrics.push({ label: "餐次", value: formatScalar(meal.meal_type, "meal_type") });
      if (meal.calories != null) metrics.push({ label: "热量", value: `${meal.calories} kcal` });
      if (meal.protein_g != null) metrics.push({ label: "蛋白", value: `${meal.protein_g}g` });
      if (meal.carbs_g != null) metrics.push({ label: "碳水", value: `${meal.carbs_g}g` });
      if (meal.fat_g != null) metrics.push({ label: "脂肪", value: `${meal.fat_g}g` });
    }
    return { metrics };
  },
  set_nutrition_goals_tool: (obj) => {
    const goals = obj?.goals as Record<string, unknown> | undefined;
    const metrics: Metric[] = [];
    if (goals) {
      if (goals.calorie_goal != null) metrics.push({ label: "热量目标", value: `${goals.calorie_goal} kcal` });
      if (goals.protein_goal_g != null) metrics.push({ label: "蛋白目标", value: `${goals.protein_goal_g}g` });
      if (goals.carbs_goal_g != null) metrics.push({ label: "碳水目标", value: `${goals.carbs_goal_g}g` });
      if (goals.fat_goal_g != null) metrics.push({ label: "脂肪目标", value: `${goals.fat_goal_g}g` });
    }
    return { metrics };
  },
  get_user_profile_tool: (obj) => {
    const metrics = buildProfileMetrics(obj?.profile as Record<string, unknown> | undefined);
    return { text: metrics.length ? "" : "暂无用户资料", metrics };
  },
  update_user_profile_tool: (obj) => {
    const metrics = buildProfileMetrics(obj?.profile as Record<string, unknown> | undefined);
    return { text: metrics.length ? "" : "用户资料已更新", metrics };
  },
  get_user_summary_tool: (obj) => {
    const body = obj?.body as Record<string, unknown> | undefined;
    const plan = obj?.plan as Record<string, unknown> | undefined;
    const streak = obj?.streak as Record<string, unknown> | undefined;
    const diet = obj?.diet as Record<string, unknown> | undefined;
    const metrics: Metric[] = [];
    if (body) {
      if (body.gender != null) metrics.push({ label: "性别", value: formatScalar(body.gender, "gender") });
      if (body.age != null) metrics.push({ label: "年龄", value: `${body.age}岁` });
      if (body.height_cm != null) metrics.push({ label: "身高", value: `${body.height_cm}cm` });
      if (body.weight_kg != null) metrics.push({ label: "体重", value: `${body.weight_kg}kg` });
      if (body.bmi != null) metrics.push({ label: "BMI", value: String(body.bmi) });
      if (body.goal != null) metrics.push({ label: "目标", value: formatScalar(body.goal, "goal") });
    }
    if (plan?.name) metrics.push({ label: "计划", value: String(plan.name) });
    if (plan?.difficulty != null) metrics.push({ label: "难度", value: formatScalar(plan.difficulty, "difficulty") });
    if (streak?.current_streak != null) metrics.push({ label: "连续打卡", value: `${streak.current_streak}天` });
    if (obj?.weekly_checkins != null) metrics.push({ label: "本周打卡", value: `${obj.weekly_checkins}次` });
    if (diet?.intake) {
      const intake = diet.intake as Record<string, unknown>;
      if (intake.total_calories != null) metrics.push({ label: "今日摄入", value: `${intake.total_calories}kcal` });
    }
    const missing = (obj?.missing_fields as string[] | undefined) ?? [];
    const text = missing.length ? `资料待完善：${missing.join("、")}` : "";
    return { text, metrics };
  },
  get_plan_detail_tool: (obj) => {
    const plan = obj?.plan as Record<string, unknown> | undefined;
    const metrics: Metric[] = [];
    if (plan) {
      if (plan.name) metrics.push({ label: "计划", value: String(plan.name) });
      if (plan.goal != null) metrics.push({ label: "目标", value: formatScalar(plan.goal, "goal") });
      if (plan.difficulty != null) metrics.push({ label: "难度", value: formatScalar(plan.difficulty, "difficulty") });
      if (plan.weeks != null) metrics.push({ label: "周数", value: `${plan.weeks}周` });
      if (plan.status) metrics.push({ label: "状态", value: formatScalar(plan.status, "status") });
    }
    return { text: metrics.length ? "" : "暂无计划详情", metrics };
  },
  read_kb_document: (obj) => {
    const doc = obj?.document as Record<string, unknown> | undefined;
    const url = doc?.url as string | undefined;
    return { text: obj?.message as string | undefined, metrics: [], detailLink: url };
  },
};

/** 卡片头部的一句话摘要 */
function getSummary(
  tc: ToolCall,
  obj: Record<string, unknown> | null,
  text: string | null
): string {
  if (tc.status === "running") return "正在执行…";
  if (tc.status === "interrupted") return "等待用户审批";
  if (tc.status === "error") return tc.error || "执行出错";
  if (obj) {
    if (obj.success === false) return String(obj.error || "执行失败");
    if (typeof obj.message === "string" && obj.message) return obj.message;
    if (typeof obj.analysis === "string" && obj.analysis) return obj.analysis;
    if (typeof obj.recommendation === "string" && obj.recommendation) return obj.recommendation;
    const extractor = statsExtractors[tc.name];
    if (extractor) {
      const r = extractor(obj);
      if (r.metrics.length) return r.metrics.map((m) => `${m.label} ${m.value}`).join(" · ");
      if (r.text) return r.text;
    }
  }
  if (text) return text.length > 60 ? `${text.slice(0, 60)}…` : text;
  return "已完成";
}

// ===== 链接组件 =====

/** 站内详情页链接（按钮样式，用于单对象区域，如 read_kb_document） */
function DetailLink({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[10px] font-medium text-emerald-700 ring-1 ring-emerald-200/60 transition-colors hover:bg-emerald-100 hover:text-emerald-800"
    >
      <ExternalLinkIcon className="size-3" />
      查看详情
    </a>
  );
}

/** 紧凑链接（用于列表项标题行右侧） */
function DetailLinkInline({ url }: { url: string }) {
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex shrink-0 items-center gap-0.5 text-[9px] font-medium text-emerald-600 transition-colors hover:text-emerald-800 hover:underline"
    >
      详情
      <ExternalLinkIcon className="size-2.5" />
    </a>
  );
}

// ===== 入参摘要 =====

/** 把 tc.input 转成「标签 值」chip 行，跳过空值/ID/嵌套对象 */
function InputSummary({ input }: { input: Record<string, unknown> }) {
  const entries = Object.entries(input).filter(
    ([k, v]) =>
      !SKIP_KEYS.has(k) &&
      !LINK_KEYS.has(k) &&
      !isIdKey(k) &&
      v !== null &&
      v !== undefined &&
      v !== "" &&
      typeof v !== "object"
  );
  if (!entries.length) return null;
  return (
    <div className="space-y-0.5">
      <p className="text-[10px] font-medium text-emerald-700/55">输入</p>
      <div className="flex flex-wrap gap-1">
        {entries.map(([k, v]) => (
          <span
            key={k}
            className="inline-flex items-baseline gap-1 rounded-md bg-white/80 px-1.5 py-0.5 text-[10px] shadow-[inset_0_0_0_1px_rgba(16,185,129,0.1)]"
          >
            <span className="text-emerald-700/55">{labelFor(k)}</span>
            <span className="font-medium text-emerald-950">{formatScalar(v, k)}</span>
          </span>
        ))}
      </div>
    </div>
  );
}

// ===== 出参：关键指标标签行 =====

function MetricRow({ metrics }: { metrics: Metric[] }) {
  if (!metrics.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {metrics.map((m, i) => (
        <span
          key={i}
          className="inline-flex items-baseline gap-1 rounded-md bg-white/80 px-1.5 py-0.5 text-[10px] shadow-[inset_0_0_0_1px_rgba(16,185,129,0.1)]"
        >
          <span className="text-emerald-700/55">{m.label}</span>
          <span className="font-medium text-emerald-950">{m.value}</span>
          {m.ok && <span className="text-emerald-600">✓</span>}
        </span>
      ))}
    </div>
  );
}

// ===== 出参：列表型查询结果项 =====

type ListConfig = { itemsKey: string; titleKey: string; tags?: string[] };

const listResultConfig: Record<string, ListConfig> = {
  search_knowledge_base: { itemsKey: "results", titleKey: "document_title" },
  list_my_knowledge_bases: { itemsKey: "knowledge_bases", titleKey: "name", tags: ["description"] },
  list_plans_tool: { itemsKey: "plans", titleKey: "name", tags: ["status", "goal"] },
  get_exercises_tool: { itemsKey: "exercises", titleKey: "name", tags: ["difficulty", "muscle_group"] },
};

function ResultItem({
  item,
  cfg,
  toolName,
}: {
  item: Record<string, unknown>;
  cfg: ListConfig;
  toolName: string;
}) {
  const title = item[cfg.titleKey];
  const explicitUrl = typeof item.url === "string" ? item.url : null;
  const kbIdUrl =
    toolName === "list_my_knowledge_bases" && typeof item.id === "string"
      ? `/knowledge-bases/${item.id}`
      : null;
  const url = explicitUrl ?? kbIdUrl;
  const tags = (cfg.tags ?? [])
    .map((k) => item[k])
    .filter((v) => v !== null && v !== undefined && v !== "");
  return (
    <div className="rounded-lg bg-white/80 px-2 py-1 shadow-[inset_0_0_0_1px_rgba(16,185,129,0.1)]">
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-[11px] font-semibold text-emerald-950">
          {title != null ? formatScalar(title, cfg.titleKey) : "—"}
        </span>
        {url && <DetailLinkInline url={url} />}
      </div>
      {tags.length > 0 && (
        <div className="mt-0.5 flex flex-wrap gap-1">
          {tags.map((t, i) => (
            <span
              key={i}
              className="rounded-full bg-emerald-50/60 px-1 py-0.5 text-[9px] text-emerald-700"
            >
              {formatScalar(t)}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ===== 出参分派 =====

const toolOutputKind: Record<string, "op" | "list" | "stats"> = {
  // 操作类：出参直接用 message（或 str）
  record_meal_tool: "op",
  manage_meal_tool: "op",
  set_nutrition_goals_tool: "op",
  checkin_tool: "op",
  get_streak_tool: "op",
  create_plan_tool: "op",
  create_diet_plan_tool: "op",
  update_plan_tool: "op",
  delete_plan_tool: "op",
  add_plan_day_tool: "op",
  remove_plan_day_tool: "op",
  sync_plan_day_tool: "op",
  add_exercise_tool: "op",
  update_exercise_tool: "op",
  remove_exercise_tool: "op",
  update_user_profile_tool: "op",
  save_preference: "op",
  save_user_fact: "op",
  save_event: "op",
  update_memory: "op",
  delete_memory: "op",
  skill_load_tool: "op",
  recall_memory: "op",
  list_user_profile: "op",
  // 列表型查询：摘要 + 结果卡片列表
  search_knowledge_base: "list",
  list_my_knowledge_bases: "list",
  list_plans_tool: "list",
  get_exercises_tool: "list",
  // 统计/单对象型查询：关键指标标签行
  query_stats_tool: "stats",
  query_diet_summary_tool: "stats",
  get_user_profile_tool: "stats",
  get_user_summary_tool: "stats",
  get_plan_detail_tool: "stats",
  read_kb_document: "stats",
};

/** 出参摘要：按工具类型三路分派 */
function OutputSummary({
  tc,
  obj,
  text,
}: {
  tc: ToolCall;
  obj: Record<string, unknown> | null;
  text: string | null;
}) {
  const kind = toolOutputKind[tc.name] ?? "op";

  if (kind === "op") {
    const msg = (obj?.message as string) || "";
    const extractor = statsExtractors[tc.name];
    const stats = extractor ? extractor(obj) : null;
    const metrics = stats?.metrics ?? [];
    const statsText = stats?.text ?? "";
    const detailLink = stats?.detailLink;
    const displayText = msg || statsText || text || "";
    const hasContent = !!displayText || metrics.length > 0 || !!detailLink;
    if (!hasContent) return null;
    return (
      <div className="space-y-1">
        {displayText && (
          <div className="space-y-0.5">
            <p className="text-[10px] font-medium text-emerald-700/55">输出</p>
            <p className="whitespace-pre-line text-[11px] leading-relaxed text-emerald-950/85">{displayText}</p>
          </div>
        )}
        {metrics.length > 0 && <MetricRow metrics={metrics} />}
        {detailLink && <DetailLink url={detailLink} />}
      </div>
    );
  }

  if (kind === "list") {
    const cfg = listResultConfig[tc.name];
    const summaryText =
      (obj?.message as string) ||
      (tc.name === "get_exercises_tool" ? (obj?.recommendation as string) : "") ||
      "";
    const rawItems = cfg && obj ? (obj[cfg.itemsKey] as unknown[] | undefined) : undefined;
    const items: Record<string, unknown>[] = (rawItems ?? [])
      .map((it) => (it && typeof it === "object" ? (it as Record<string, unknown>) : null))
      .filter((x): x is Record<string, unknown> => x !== null);
    return (
      <div className="space-y-1">
        {summaryText && (
          <div className="space-y-0.5">
            <p className="text-[10px] font-medium text-emerald-700/55">输出</p>
            <p className="text-[11px] leading-relaxed text-emerald-950/85">{summaryText}</p>
          </div>
        )}
        {items.length > 0 && cfg && (
          <div className="space-y-1">
            <p className="text-[10px] font-medium text-emerald-700/55">
              结果（{items.length}）
            </p>
            <div className="space-y-1">
              {items.map((it, i) => (
                <ResultItem key={i} item={it} cfg={cfg} toolName={tc.name} />
              ))}
            </div>
          </div>
        )}
      </div>
    );
  }

  // stats
  const extractor = statsExtractors[tc.name];
  const result = extractor ? extractor(obj) : null;
  if (!result) return null;
  const hasContent = !!result.text || result.metrics.length > 0 || !!result.detailLink;
  if (!hasContent) return null;
  return (
    <div className="space-y-1">
      {result.text && (
        <div className="space-y-0.5">
          <p className="text-[10px] font-medium text-emerald-700/55">输出</p>
          <p className="text-[11px] leading-relaxed text-emerald-950/85">{result.text}</p>
        </div>
      )}
      {result.metrics.length > 0 && <MetricRow metrics={result.metrics} />}
      {result.detailLink && <DetailLink url={result.detailLink} />}
    </div>
  );
}

/**
 * 工具调用卡片：把一次 Tool 调用封装为面向用户的可读卡片。
 *
 * - 头部：图标 + 中文名 + 状态徽标 + 一句话摘要，始终可见（可点击折叠正文）
 * - 正文：入参摘要（标签行）+ 出参摘要（按工具类型分派：message / 结果列表 / 关键指标）
 * - 不展示原始 JSON、字段字典、content 大文本
 *
 * embedded 模式：嵌入 ChainOfThought 步骤节点时使用，仅渲染正文
 *（无卡片外壳与头部，节点标题/图标/状态由外层步骤承载，避免重复）。
 */
export function ToolCallCard({ tc, embedded = false }: { tc: ToolCall; embedded?: boolean }) {
  const { obj, text } = useMemo(() => parseOutput(tc.output), [tc.output]);

  const running = tc.status === "running";
  const interrupted = tc.status === "interrupted";
  const failed = tc.status === "error" || obj?.success === false;
  const hasInput = !!tc.input && Object.keys(tc.input).length > 0;
  const showBody = hasInput || !running;

  const [open, setOpen] = useState(false);

  const Icon = toolIconMap[tc.name] ?? WrenchIcon;
  const title = toolNameMap[tc.name] ?? tc.name;
  const tint = iconTintMap[tc.name] ?? "from-emerald-500 to-teal-600";
  const summary = getSummary(tc, obj, text);
  const errorMsg = failed
    ? tc.error || (obj && String(obj.error || "")) || "执行失败"
    : "";

  const body = (
    <div className="space-y-1.5">
      {hasInput && <InputSummary input={tc.input} />}
      {!running && failed && errorMsg && (
        <div className="flex items-start gap-1.5 rounded-md bg-red-50 px-2 py-1.5 text-[11px] leading-relaxed text-red-700 ring-1 ring-red-200/60">
          <XCircleIcon className="mt-0.5 size-3 shrink-0" />
          <span>{errorMsg}</span>
        </div>
      )}
      {!running && !failed && <OutputSummary tc={tc} obj={obj} text={text} />}
    </div>
  );

  if (embedded) {
    if (!showBody) return null;
    return <div className="not-prose w-full space-y-2">{body}</div>;
  }

  const header = (
    <div className="flex w-full items-center gap-2 px-2 py-1.5 text-left">
      <span
        className={cn(
          "flex size-6 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm",
          tint,
          running && "animate-pulse"
        )}
      >
        <Icon className="size-3.5" />
      </span>
      <span className="flex min-w-0 flex-1 flex-col gap-0.5">
        <span className="flex items-center gap-1.5">
          <span className="truncate text-xs font-semibold text-emerald-950">{title}</span>
          {running ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-amber-50 px-1 py-0.5 text-[9px] font-medium text-amber-700 ring-1 ring-amber-200/70">
              <Loader2Icon className="size-2.5 animate-spin" />
              执行中
            </span>
          ) : interrupted ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-slate-50 px-1 py-0.5 text-[9px] font-medium text-slate-600 ring-1 ring-slate-200/70">
              <ClockIcon className="size-2.5" />
              待审批
            </span>
          ) : failed ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-red-50 px-1 py-0.5 text-[9px] font-medium text-red-700 ring-1 ring-red-200/70">
              <XCircleIcon className="size-2.5" />
              失败
            </span>
          ) : (
            <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-emerald-50 px-1 py-0.5 text-[9px] font-medium text-emerald-700 ring-1 ring-emerald-200/70">
              <CheckCircle2Icon className="size-2.5" />
              完成
            </span>
          )}
        </span>
        <span
          className={cn(
            "truncate text-[11px]",
            failed ? "text-red-600/80" : "text-emerald-700/60"
          )}
        >
          {summary}
        </span>
      </span>
      {showBody && (
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
            : interrupted
              ? "border-slate-200/80 border-l-2 border-l-slate-400"
              : "border-emerald-100 border-l-2 border-l-emerald-400 hover:shadow-md hover:shadow-emerald-900/[0.06]"
      )}
    >
      {showBody ? (
        <Collapsible open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger className="block w-full transition-colors hover:bg-emerald-50/50">
            {header}
          </CollapsibleTrigger>
          {open && (
            <CollapsibleContent>
              <div className="border-t border-emerald-100/70 bg-emerald-50/40 px-2 py-2">
                {body}
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
