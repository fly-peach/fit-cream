/**
 * 动作库相关标签映射
 *
 * 与后端种子数据字段值对齐，供动作库页面与计划编辑界面共用。
 * dataset（© Gym visual 1324 动作）的原始值为英文，中文通过映射表翻译；
 * 英文模式直接展示格式化后的原始值。
 */
import { useCallback } from "react";
import { useLanguage } from "@/lib/language-context";

export const muscleGroupLabels: Record<string, string> = {
  chest: "胸部",
  back: "背部",
  legs: "腿部",
  shoulders: "肩部",
  arms: "手臂",
  core: "核心",
  full_body: "全身",
};

// dataset body_part（10 种，精细分类）
export const bodyPartLabels: Record<string, string> = {
  chest: "胸部",
  back: "背部",
  shoulders: "肩部",
  neck: "颈部",
  "upper arms": "上臂",
  "lower arms": "前臂",
  "upper legs": "大腿",
  "lower legs": "小腿",
  waist: "腰部",
  cardio: "有氧",
};

// dataset muscle_group（协同肌，29 种）
export const muscleSubgroupLabels: Record<string, string> = {
  abdominals: "腹直肌",
  "ankle stabilizers": "踝稳定肌",
  ankles: "踝关节",
  biceps: "肱二头肌",
  calves: "小腿",
  chest: "胸部",
  core: "核心",
  deltoids: "三角肌",
  forearms: "前臂",
  glutes: "臀大肌",
  hamstrings: "腘绳肌",
  hands: "手部",
  "hip flexors": "髋屈肌",
  "latissimus dorsi": "背阔肌",
  lats: "背阔肌",
  "lower back": "下背部",
  obliques: "腹斜肌",
  quadriceps: "股四头肌",
  rhomboids: "菱形肌",
  "rotator cuff": "肩袖",
  shoulders: "肩部",
  soleus: "比目鱼肌",
  trapezius: "斜方肌",
  traps: "斜方肌",
  triceps: "肱三头肌",
  "upper back": "上背部",
  "wrist extensors": "腕伸肌",
  "wrist flexors": "腕屈肌",
  wrists: "腕关节",
};

// dataset equipment（28 种，原始值不归一化）
export const equipmentLabels: Record<string, string> = {
  assisted: "助力",
  band: "弹力带",
  barbell: "杠铃",
  "body weight": "自重",
  "bosu ball": "波速球",
  cable: "绳索",
  dumbbell: "哑铃",
  "elliptical machine": "椭圆机",
  "ez barbell": "EZ 杠铃",
  hammer: "锤",
  kettlebell: "壶铃",
  "leverage machine": "杠杆器械",
  "medicine ball": "药球",
  "olympic barbell": "奥运杠铃",
  "resistance band": "阻力带",
  roller: "滚轮",
  rope: "绳索",
  "skierg machine": "滑雪机",
  "sled machine": "推雪橇机",
  "smith machine": "史密斯机",
  "stability ball": "稳定球",
  "stationary bike": "动感单车",
  "stepmill machine": "台阶机",
  tire: "轮胎",
  "trap bar": "六角杠铃",
  "upper body ergometer": "上肢测功仪",
  weighted: "负重",
  "wheel roller": "滚轮",
};

// dataset target（19 种）
export const targetLabels: Record<string, string> = {
  abductors: "外展肌",
  abs: "腹肌",
  adductors: "内收肌",
  biceps: "肱二头肌",
  calves: "小腿",
  "cardiovascular system": "心血管系统",
  delts: "三角肌",
  forearms: "前臂",
  glutes: "臀大肌",
  hamstrings: "腘绳肌",
  lats: "背阔肌",
  "levator scapulae": "肩胛提肌",
  pectorals: "胸肌",
  quads: "股四头肌",
  "serratus anterior": "前锯肌",
  spine: "脊柱",
  traps: "斜方肌",
  triceps: "肱三头肌",
  "upper back": "上背部",
};

export const difficultyLabels: Record<string, string> = {
  beginner: "入门",
  intermediate: "进阶",
  advanced: "高级",
};

export const difficultyColors: Record<string, string> = {
  beginner: "border-emerald-200 bg-emerald-50 text-emerald-700",
  intermediate: "border-amber-200 bg-amber-50 text-amber-700",
  advanced: "border-red-200 bg-red-50 text-red-700",
};

export const categoryLabels: Record<string, string> = {
  compound: "复合",
  isolation: "孤立",
  cardio: "有氧",
  mobility: "灵活性",
};

/** 取标签，缺省回退为原始值（中文映射） */
export function labelOf(
  map: Record<string, string>,
  value?: string | null,
): string | null {
  if (!value) return null;
  return map[value] ?? value;
}

/** 英文原始值格式化："upper arms" -> "Upper Arms" */
export function formatEnLabel(value: string): string {
  return value.replace(/\b[a-z]/g, (c) => c.toUpperCase());
}

/** 按语言取标签：中文查映射表，英文用格式化原始值 */
export function labelOfLang(
  map: Record<string, string>,
  value: string | null | undefined,
  isZh: boolean,
): string | null {
  if (!value) return null;
  return isZh ? (map[value] ?? value) : formatEnLabel(value);
}

/** Hook：返回绑定当前语言的 labelOf */
export function useLabel() {
  const { isZh } = useLanguage();
  return useCallback(
    (map: Record<string, string>, value?: string | null) =>
      labelOfLang(map, value, isZh),
    [isZh],
  );
}
