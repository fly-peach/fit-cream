/**
 * Intake 信息采集表单模板
 *
 * 模板定义在前端（字段/类型/选项），后端 present_form_tool 只传
 * form_id + 已知字段预填值，FormCard 按模板自动渲染。
 *
 * 全部模板提交后均落库：body_profile 由 agent 调 update_user_profile_tool，
 * 五维（health_safety/fitness_level/exercise_history/lifestyle/diet_profile）
 * 由 agent 调 update_fitness_profile_tool，baseline 由 record_baseline_tool。
 */

export type FormFieldType = "number" | "text" | "textarea" | "select";

export interface FormFieldOption {
  value: string;
  label: string;
}

export interface FormFieldDef {
  key: string;
  label: string;
  type: FormFieldType;
  options?: FormFieldOption[];
  placeholder?: string;
  hint?: string;
  unit?: string;
  required?: boolean;
}

export interface FormTemplate {
  id: string;
  title: string;
  fields: FormFieldDef[];
  hint?: string;
}

const GOAL_OPTIONS: FormFieldOption[] = [
  { value: "lose_fat", label: "减脂" },
  { value: "gain_muscle", label: "增肌" },
  { value: "maintain", label: "保持健康" },
  { value: "improve_health", label: "改善体质" },
];

const GENDER_OPTIONS: FormFieldOption[] = [
  { value: "male", label: "男" },
  { value: "female", label: "女" },
  { value: "other", label: "其他" },
];

export const FORM_TEMPLATES: Record<string, FormTemplate> = {
  body_profile: {
    id: "body_profile",
    title: "基础身体数据",
    fields: [
      { key: "height_cm", label: "身高", type: "number", unit: "cm", required: true, placeholder: "如 175" },
      { key: "weight_kg", label: "体重", type: "number", unit: "kg", required: true, placeholder: "如 70" },
      { key: "age", label: "年龄", type: "number", unit: "岁", required: true, placeholder: "如 25" },
      { key: "gender", label: "性别", type: "select", options: GENDER_OPTIONS, required: true },
      { key: "goal", label: "健身目标", type: "select", options: GOAL_OPTIONS, required: true },
    ],
  },

  health_safety: {
    id: "health_safety",
    title: "健康与安全基线",
    fields: [
      {
        key: "medical_history",
        label: "既往病史与当前健康状况",
        type: "textarea",
        required: true,
        placeholder: "如：高血压、糖尿病等慢性病，无则填「无」",
      },
      {
        key: "injuries",
        label: "伤病与身体限制",
        type: "textarea",
        required: true,
        placeholder: "如：膝盖旧伤、腰背不适、关节活动受限，无则填「无」",
      },
      {
        key: "allergies",
        label: "过敏史与食物不耐",
        type: "text",
        placeholder: "如：海鲜过敏、乳糖不耐受，无则留空",
      },
      {
        key: "pregnancy",
        label: "孕期/产后状态",
        type: "text",
        placeholder: "女性是否处于孕期、备孕或产后阶段，无关则留空",
      },
      {
        key: "medication",
        label: "用药情况",
        type: "text",
        required: true,
        placeholder: "正在服用的药物（可能影响运动生理反应），无则填「无」",
      },
      {
        key: "parq_result",
        label: "PAR-Q 运动风险自查",
        type: "select",
        required: true,
        hint: "运动中是否出现过胸痛、头晕、关节疼痛等不适？",
        options: [
          { value: "low", label: "无上述情况（低风险）" },
          { value: "uncertain", label: "不确定" },
          { value: "high", label: "有上述情况（建议先咨询医生）" },
        ],
      },
      {
        key: "doctor_advice",
        label: "医生建议（如有）",
        type: "text",
        placeholder: "医生的运动许可或限制说明",
      },
    ],
  },

  fitness_level: {
    id: "fitness_level",
    title: "当前体能水平",
    fields: [
      {
        key: "training_experience",
        label: "系统训练经验",
        type: "select",
        required: true,
        options: [
          { value: "never", label: "从未系统训练" },
          { value: "beginner", label: "初学者（不足 1 年）" },
          { value: "intermediate", label: "进阶（1-3 年）" },
          { value: "advanced", label: "资深（3 年以上）" },
        ],
      },
      {
        key: "cardio_level",
        label: "心肺耐力",
        type: "select",
        required: true,
        hint: "连续快走或慢跑 20 分钟的轻松程度",
        options: [
          { value: "beginner", label: "吃力（走几步就喘）" },
          { value: "intermediate", label: "可以完成但较累" },
          { value: "advanced", label: "轻松完成" },
        ],
      },
      {
        key: "strength_level",
        label: "力量水平",
        type: "select",
        required: true,
        options: [
          { value: "beginner", label: "入门（俯卧撑不足 10 个）" },
          { value: "intermediate", label: "中等（俯卧撑 10-30 个）" },
          { value: "advanced", label: "良好（俯卧撑 30 个以上或有举铁基础）" },
        ],
      },
      {
        key: "flexibility",
        label: "柔韧性",
        type: "select",
        options: [
          { value: "limited", label: "较受限（弯腰摸不到脚尖）" },
          { value: "normal", label: "正常" },
          { value: "good", label: "良好" },
        ],
      },
      {
        key: "body_fat_pct",
        label: "体脂率（如知道）",
        type: "number",
        unit: "%",
        placeholder: "如 22，不知道可留空",
      },
    ],
  },

  exercise_history: {
    id: "exercise_history",
    title: "运动经历与习惯",
    fields: [
      {
        key: "weekly_frequency",
        label: "当前每周运动次数",
        type: "select",
        required: true,
        options: [
          { value: "0", label: "几乎不运动" },
          { value: "1-2", label: "1-2 次" },
          { value: "3-4", label: "3-4 次" },
          { value: "5+", label: "5 次以上" },
        ],
      },
      {
        key: "session_duration",
        label: "每次运动时长",
        type: "select",
        options: [
          { value: "<30", label: "30 分钟以内" },
          { value: "30-60", label: "30-60 分钟" },
          { value: ">60", label: "1 小时以上" },
        ],
      },
      {
        key: "preferred_types",
        label: "常做/喜欢的运动",
        type: "text",
        placeholder: "如：跑步、撸铁、游泳、球类",
      },
      {
        key: "past_results",
        label: "过往训练成果",
        type: "textarea",
        placeholder: "过去是否取得过显著的健身成果？",
      },
    ],
  },

  diet_profile: {
    id: "diet_profile",
    title: "饮食偏好与结构",
    fields: [
      {
        key: "diet_preferences",
        label: "饮食偏好",
        type: "text",
        required: true,
        placeholder: "如：少油清淡、爱吃肉、素食为主",
      },
      {
        key: "food_allergies",
        label: "忌口/过敏",
        type: "text",
        placeholder: "如：海鲜过敏、不吃辣、乳糖不耐受",
      },
      {
        key: "cooking_condition",
        label: "烹饪条件/时间",
        type: "text",
        placeholder: "如：早餐外食、午餐食堂、晚餐可自炊，做饭 30 分钟内",
      },
      {
        key: "meals_per_day",
        label: "每日餐次",
        type: "select",
        required: true,
        options: [
          { value: "2", label: "2 餐" },
          { value: "3", label: "3 餐" },
          { value: "4", label: "4 餐" },
          { value: "5+", label: "5 餐以上" },
        ],
      },
      {
        key: "eating_out_ratio",
        label: "外食 vs 自炊比例",
        type: "select",
        options: [
          { value: "mostly_out", label: "基本外食" },
          { value: "half", label: "各一半" },
          { value: "mostly_home", label: "基本自炊" },
        ],
      },
      {
        key: "budget",
        label: "每日饮食预算",
        type: "text",
        placeholder: "如：50 元/天，不确定可留空",
      },
    ],
  },

  baseline: {
    id: "baseline",
    title: "基线评测数据",
    hint: "提交后将写入基线评测档案（力量参考动作与身体围度），用于定训练强度与后续复测追踪",
    fields: [
      {
        key: "reference_lifts",
        label: "力量参考动作（如有）",
        type: "textarea",
        placeholder: "如：卧推 60kg/深蹲 80kg/硬拉 90kg，未练过可留空",
      },
      {
        key: "circumference",
        label: "身体围度（如知道）",
        type: "text",
        placeholder: "如：腰围 80cm、臂围 35cm、胸围 95cm",
      },
    ],
  },

  lifestyle: {
    id: "lifestyle",
    title: "生活方式与客观环境",
    fields: [
      {
        key: "occupation_schedule",
        label: "职业与作息",
        type: "text",
        placeholder: "如：久坐办公，晚上有空；常出差",
      },
      {
        key: "diet_habits",
        label: "饮食习惯",
        type: "textarea",
        placeholder: "如：外卖为主、口味偏咸、不吃早餐",
      },
      {
        key: "sleep_quality",
        label: "睡眠质量",
        type: "select",
        required: true,
        options: [
          { value: "poor", label: "较差（不足 6 小时或经常醒）" },
          { value: "normal", label: "一般（6-7 小时）" },
          { value: "good", label: "良好（7 小时以上）" },
        ],
      },
      {
        key: "stress_level",
        label: "压力水平",
        type: "select",
        required: true,
        options: [
          { value: "low", label: "较低" },
          { value: "medium", label: "中等" },
          { value: "high", label: "较高" },
        ],
      },
      {
        key: "equipment",
        label: "可用训练设备/场地",
        type: "text",
        required: true,
        placeholder: "如：健身房、家用哑铃、无器械",
      },
      {
        key: "preferred_time",
        label: "偏好训练时段",
        type: "select",
        options: [
          { value: "morning", label: "早晨" },
          { value: "noon", label: "中午" },
          { value: "evening", label: "晚上" },
          { value: "flexible", label: "灵活" },
        ],
      },
    ],
  },
};
