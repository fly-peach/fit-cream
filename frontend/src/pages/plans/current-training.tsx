import {
  PlayCircle,
  Clock,
  Dumbbell,
  ImageOff,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { resolveStaticUrl } from "@/lib/api-url";
import { cn } from "@/lib/utils";
import type { PlanDay } from "./types";

export function CurrentTraining({
  day,
  dateLabel,
  completedPdeIds,
}: {
  day: PlanDay | null;
  dateLabel: string;
  completedPdeIds: Set<string>;
}) {
  const exercises = day
    ? [...day.exercises].sort((a, b) => a.sort_order - b.sort_order)
    : [];

  const gifCount = exercises.filter(
    (ex) => ex.exercise?.gif_url || ex.exercise?.image,
  ).length;

  return (
    <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-emerald-950">
            <PlayCircle className="size-4 text-emerald-500" />
            当前训练
          </CardTitle>
        </div>
        <p className="mt-1 text-xs text-emerald-600/70">
          {dateLabel}
          {day ? ` · ${day.focus || "综合训练"}` : ""}
        </p>
      </CardHeader>
      <CardContent>
        {!day || exercises.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-10 text-center">
            <Dumbbell className="size-7 text-emerald-300" />
            <p className="text-sm text-emerald-600/60">当前无训练动作</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-2 xl:grid-cols-3">
            {exercises.map((ex) => {
              const gif = resolveStaticUrl(ex.exercise?.gif_url ?? ex.exercise?.image ?? "");
              const checked = completedPdeIds.has(ex.id);
              const isCardio = ex.exercise_type === "cardio";
              return (
                <div
                  key={ex.id}
                  className={cn(
                    "overflow-hidden rounded-lg border border-emerald-100 bg-white",
                    checked && "opacity-70",
                  )}
                >
                  <div className="relative aspect-square w-full overflow-hidden bg-emerald-50">
                    {gif ? (
                      <img
                        src={gif}
                        alt={ex.exercise_name ?? "动作"}
                        loading="lazy"
                        className="h-full w-full object-cover"
                      />
                    ) : (
                      <div className="flex h-full w-full flex-col items-center justify-center gap-1 text-emerald-300">
                        <ImageOff className="size-6" />
                        <span className="px-2 text-center text-[10px]">
                          暂无动图
                        </span>
                      </div>
                    )}
                    {checked && (
                      <span className="absolute right-1 top-1 rounded-full bg-emerald-500 px-1.5 py-0.5 text-[9px] font-medium text-white">
                        ✓ 完成
                      </span>
                    )}
                  </div>
                  <div className="space-y-0.5 p-2">
                    <p className="truncate text-xs font-medium text-emerald-900">
                      {ex.exercise_name ?? "未知动作"}
                    </p>
                    <p className="truncate text-[10px] text-emerald-600/70">
                      {isCardio
                        ? `${ex.duration_min ?? 0} 分钟${ex.distance_km ? ` · ${ex.distance_km} km` : ""}`
                        : `${ex.sets ?? "-"} 组 × ${ex.reps ?? "-"} 次${ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}`}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        )}
        {day && exercises.length > 0 && (
          <div className="mt-3 flex items-center justify-between rounded-lg bg-emerald-50 px-2 py-1 text-xs text-emerald-700 lg:px-3 lg:py-2">
            <span className="flex items-center gap-1.5">
              <Clock className="size-3.5" />
              组间休息 {day.rest_seconds}s
            </span>
            <span>
              动作图示 {gifCount}/{exercises.length}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
