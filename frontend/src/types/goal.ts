/**
 * 身材原型/动作组类型定义
 *
 * 与后端 `rogers/app/routers/goal_knowledge.py` 的 /goal-knowledge/groups 输出对齐。
 */

export interface GoalMetric {
  metric: string;
  min?: number | null;
  max?: number | null;
  core?: boolean;
}

export interface GoalExerciseGoal {
  metric: string;
  display: string;
}

export interface GoalExerciseItem {
  id: string;
  name: string;
  name_en?: string | null;
  image?: string | null;
  gif_url?: string | null;
  muscle_group?: string | null;
  equipment?: string | null;
  equipment_zh?: string | null;
  difficulty?: string | null;
}

export interface GoalExerciseGroupEntry {
  group: string | null;
  exercises: GoalExerciseItem[];
}

export interface GoalExerciseGroupCard {
  key: string;
  gender: string;
  name: string;
  tagline?: string | null;
  description?: string | null;
  image?: string | null;
  target_metrics: GoalMetric[];
  target_exercise_goal: GoalExerciseGoal[];
  target_exercises: { group: string | null; exercises: string[] }[];
  exercise_groups: GoalExerciseGroupEntry[];
  training_bias?: string | null;
  diet_bias?: string | null;
  stage_hint?: string | null;
  stage_narrative_hint?: string | null;
  display_order: number;
}

export interface GoalGroupsResponse {
  gender: string;
  groups: GoalExerciseGroupCard[];
}
