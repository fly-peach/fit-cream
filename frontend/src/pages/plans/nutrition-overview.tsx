import { useMemo } from "react";
import {
  RadialBarChart,
  RadialBar,
  PolarAngleAxis,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Flame, Check, UtensilsCrossed } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DietMeal, UserSettings } from "./types";

const macroMeta: {
  key: "protein" | "carbs" | "fat";
  label: string;
  color: string;
  unit: string;
}[] = [
  { key: "protein", label: "蛋白质", color: "bg-emerald-500", unit: "g" },
  { key: "carbs", label: "碳水", color: "bg-amber-500", unit: "g" },
  { key: "fat", label: "脂肪", color: "bg-sky-500", unit: "g" },
];

function MacroBar({
  label,
  value,
  target,
  color,
  unit,
}: {
  label: string;
  value: number;
  target: number;
  color: string;
  unit: string;
}) {
  const pct = target > 0 ? Math.min(100, Math.round((value / target) * 100)) : 0;
  const met = target > 0 && value >= target;
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="flex items-center gap-1 font-medium text-orange-800">
          {label}
          {met && <Check className="size-3 text-emerald-500" />}
        </span>
        <span className="tabular-nums text-orange-600/70">
          {Math.round(value * 10) / 10}
          <span className="text-orange-400"> / {target}</span> {unit}
        </span>
      </div>
      <div className="h-2 overflow-hidden rounded-full bg-orange-100/70">
        <div
          className={cn("h-full rounded-full transition-all duration-500", color)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function NutritionOverview({
  meals,
  settings,
  dateLabel,
}: {
  meals: DietMeal[];
  settings: UserSettings | null;
  dateLabel: string;
}) {
  const totals = useMemo(
    () =>
      meals.reduce(
        (acc, m) => ({
          calories: acc.calories + (m.calories ?? 0),
          protein: acc.protein + (m.protein_g ?? 0),
          carbs: acc.carbs + (m.carbs_g ?? 0),
          fat: acc.fat + (m.fat_g ?? 0),
        }),
        { calories: 0, protein: 0, carbs: 0, fat: 0 },
      ),
    [meals],
  );

  const targetCalories = settings?.calorie_goal ?? 2000;
  const calPct =
    targetCalories > 0
      ? Math.min(100, Math.round((totals.calories / targetCalories) * 100))
      : 0;

  const goalFor = (key: "protein" | "carbs" | "fat") =>
    key === "protein"
      ? settings?.protein_goal_g ?? 0
      : key === "carbs"
        ? settings?.carbs_goal_g ?? 0
        : settings?.fat_goal_g ?? 0;

  return (
    <Card className="border-orange-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-orange-950">
            <Flame className="size-4 text-orange-500" />
            当日营养概览
          </CardTitle>
          <span className="text-xs text-orange-600/70">{dateLabel}</span>
        </div>
      </CardHeader>
      <CardContent>
        {meals.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <UtensilsCrossed className="size-7 text-orange-300" />
            <p className="text-sm text-orange-600/60">当天暂无饮食安排</p>
            <p className="text-xs text-orange-400/70">在下方「当日饮食」添加餐食后自动统计</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-6 sm:flex-row sm:items-center">
            <div className="relative size-36 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <RadialBarChart
                  innerRadius="72%"
                  outerRadius="100%"
                  data={[{ name: "calories", value: calPct, fill: "#f97316" }]}
                  startAngle={90}
                  endAngle={-270}
                >
                  <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
                  <RadialBar
                    background={{ fill: "#ffedd5" }}
                    cornerRadius={10}
                    dataKey="value"
                  />
                </RadialBarChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="text-2xl font-bold tabular-nums text-orange-950">
                  {totals.calories}
                </span>
                <span className="text-[11px] text-orange-600/70">
                  / {targetCalories} kcal
                </span>
              </div>
            </div>

            <div className="w-full flex-1 space-y-3">
              {macroMeta.map((m) => (
                <MacroBar
                  key={m.key}
                  label={m.label}
                  value={totals[m.key]}
                  target={goalFor(m.key)}
                  color={m.color}
                  unit={m.unit}
                />
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
