/**
 * 身材原型/动作组标签映射与指标格式化
 *
 * 指标词表与后端 `rogers/src/fitme/schemas/goal.py`（METRIC_KEYS）及
 * seeds/goal_knowledge.json v2 的 target_metrics 展示维度对齐。
 */
import type { GoalMetric } from "@/types/goal";

export const goalMetricLabelsZh: Record<string, string> = {
  body_fat_pct: "体脂率",
  visceral_fat_level: "内脏脂肪",
  muscle_pct: "肌肉率",
  skeletal_muscle_pct: "骨骼肌率",
  body_water_pct: "水分率",
  protein_pct: "蛋白质率",
  bone_mass_kg: "骨量",
  bmr_kcal: "基础代谢",
  body_age: "体龄",
  bmi: "BMI",
  waist_cm: "腰围",
  bench_ratio: "卧推/体重",
  squat_ratio: "深蹲/体重",
  deadlift_ratio: "硬拉/体重",
  ohp_ratio: "推举/体重",
  pull_ups: "引体向上",
  bench_kg: "卧推",
  squat_kg: "深蹲",
  deadlift_kg: "硬拉",
  ohp_kg: "推举",
  bodyweight_kg: "体重",
};

export const goalMetricLabelsEn: Record<string, string> = {
  body_fat_pct: "Body fat",
  visceral_fat_level: "Visceral fat",
  muscle_pct: "Muscle %",
  skeletal_muscle_pct: "Skeletal muscle %",
  body_water_pct: "Water %",
  protein_pct: "Protein %",
  bone_mass_kg: "Bone mass",
  bmr_kcal: "BMR",
  body_age: "Body age",
  bmi: "BMI",
  waist_cm: "Waist",
  bench_ratio: "Bench/bw",
  squat_ratio: "Squat/bw",
  deadlift_ratio: "Deadlift/bw",
  ohp_ratio: "OHP/bw",
  pull_ups: "Pull-ups",
  bench_kg: "Bench",
  squat_kg: "Squat",
  deadlift_kg: "Deadlift",
  ohp_kg: "OHP",
  bodyweight_kg: "Bodyweight",
};

const goalMetricUnits: Record<string, string> = {
  body_fat_pct: "%",
  muscle_pct: "%",
  skeletal_muscle_pct: "%",
  body_water_pct: "%",
  protein_pct: "%",
  waist_cm: "cm",
  bone_mass_kg: "kg",
  bmr_kcal: "kcal",
  body_age: "岁",
  bench_ratio: "×",
  squat_ratio: "×",
  deadlift_ratio: "×",
  ohp_ratio: "×",
  pull_ups: "个",
  bench_kg: "kg",
  squat_kg: "kg",
  deadlift_kg: "kg",
  ohp_kg: "kg",
  bodyweight_kg: "kg",
};

/** 动作组组名（种子为中文）→ 英文 */
export const goalGroupLabelsEn: Record<string, string> = {
  胸: "Chest",
  背: "Back",
  肩: "Shoulders",
  腿: "Legs",
  核心: "Core",
  手臂: "Arms",
  臀腿: "Glutes & Legs",
  上肢轻量: "Upper (light)",
  拉伸: "Stretching",
};

/** 指标名标签（按语言） */
export function goalMetricLabel(metric: string, isZh: boolean): string {
  return isZh
    ? (goalMetricLabelsZh[metric] ?? metric)
    : (goalMetricLabelsEn[metric] ?? metric);
}

/** 组名标签（按语言，英文回退原中文） */
export function goalGroupLabel(group: string | null, isZh: boolean): string {
  if (!group) return "";
  return isZh ? group : (goalGroupLabelsEn[group] ?? group);
}

/** 指标区间为人读文案："体脂率 10-14%" / "腰围 ≤80cm" / "引体向上 ≥8个" */
export function formatGoalMetric(m: GoalMetric, isZh: boolean): string {
  const label = goalMetricLabel(m.metric, isZh);
  const unit = goalMetricUnits[m.metric] ?? "";
  const fmt = (v: number) => `${Number.isInteger(v) ? v : v.toFixed(1)}${unit}`;
  if (m.min != null && m.max != null) return `${label} ${fmt(m.min)}-${fmt(m.max)}`;
  if (m.min != null) return `${label} ≥${fmt(m.min)}`;
  if (m.max != null) return `${label} ≤${fmt(m.max)}`;
  return label;
}
