import type { ExerciseBrief } from "@/types/exercise";

export interface PlanExercise {
  id: string;
  exercise_id: string | null;
  custom_name?: string | null;
  exercise_name: string | null;
  exercise_type?: "strength" | "cardio" | null;
  sets: number | null;
  reps: number | null;
  weight_kg: number | null;
  duration_min?: number | null;
  distance_km?: number | null;
  calories_per_min?: number | null;
  sort_order: number;
  notes?: string | null;
  metadata_?: Record<string, string> | null;
  exercise?: ExerciseBrief | null;
}

export interface PlanDay {
  id: string;
  day_of_week: number;
  focus: string | null;
  rest_seconds: number;
  metadata_?: Record<string, string> | null;
  exercises: PlanExercise[];
}

export interface PlanDetail {
  id: string;
  name: string;
  goal: string | null;
  difficulty: string | null;
  weeks: number | null;
  status: string;
  days: PlanDay[];
}

export interface CheckinExerciseItem {
  id: string;
  exercise_id: string | null;
  custom_name?: string | null;
  plan_day_exercise_id: string | null;
  sets_done: number | null;
  reps_done: number | null;
  weight_kg: number | null;
  duration_min: number | null;
  distance_km: number | null;
}

export interface CheckinItem {
  id: string;
  date: string;
  plan_day_id?: string | null;
  duration_min: number | null;
  exercises: CheckinExerciseItem[];
}

export interface DietMeal {
  id: string;
  meal_type: string;
  food_name: string;
  calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
  portion: string | null;
  sort_order: number;
  metadata_?: Record<string, string> | null;
}

export interface DietDay {
  id: string;
  day_of_week: number;
  focus: string | null;
  meals: DietMeal[];
  metadata_?: Record<string, string> | null;
}

export interface DietPlanDetail {
  id: string;
  name: string;
  target_calories: number | null;
  goal: string | null;
  status: string;
  days: DietDay[];
}

export interface UserSettings {
  calorie_goal: number;
  protein_goal_g: number;
  carbs_goal_g: number;
  fat_goal_g: number;
}

export const dayNames = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export const mealTypeLabels: Record<string, string> = {
  breakfast: "早餐",
  lunch: "午餐",
  dinner: "晚餐",
  snack: "加餐",
};

export const mealTypeColors: Record<string, string> = {
  breakfast: "bg-amber-100 text-amber-700",
  lunch: "bg-emerald-100 text-emerald-700",
  dinner: "bg-sky-100 text-sky-700",
  snack: "bg-purple-100 text-purple-700",
};

export type CalMode = "exercise" | "diet";

export function parseDateLocal(s: string): Date {
  const [y, m, d] = s.split("-").map(Number);
  return new Date(y, (m ?? 1) - 1, d ?? 1);
}

export function dateToDow(d: Date): number {
  return ((d.getDay() + 6) % 7) + 1;
}
