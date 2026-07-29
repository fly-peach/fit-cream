/**
 * 动作库类型定义
 *
 * 与后端 `rogers/src/fitme/schemas/exercise.py` 对齐：
 * - ExerciseBrief: 嵌入计划/打卡场景的摘要输出
 * - Exercise: 完整动作输出（ExerciseOut）
 */

export interface ExerciseBrief {
  name: string;
  name_en?: string | null;
  muscle_group?: string | null;
  muscle_subgroup?: string | null;
  muscle_subgroup_zh?: string | null;
  category?: string | null;
  is_compound: boolean;
  equipment?: string | null;
  equipment_zh?: string | null;
  difficulty?: string | null;
  description?: string | null;
  body_part?: string | null;
  body_part_zh?: string | null;
  target?: string | null;
  target_zh?: string | null;
  image?: string | null;
}

export interface Exercise extends ExerciseBrief {
  id: string;
  calories_per_min?: number | null;
  instructions?: string | null;
  tips?: string | null;
  secondary_muscles?: string[] | null;
  secondary_muscles_zh?: string[] | null;
  instruction_steps?: string[] | null;
  instruction_steps_en?: string[] | null;
  instructions_en?: string | null;
  media_id?: string | null;
  gif_url?: string | null;
  attribution?: string | null;
}

export interface CategoryStats {
  name: string;
  count: number;
}

export interface MuscleGroupStats {
  name: string;
  count: number;
}

export interface EquipmentStats {
  name: string;
  count: number;
}
