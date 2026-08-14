import { useEffect, useMemo, useState } from "react";
import { Loader2, Gauge, Flame } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";

interface ActivityLevel {
  value: string;
  label: string;
  factor: number;
}

interface ActivityTargets {
  activity_label: string;
  bmr: number | null;
  tdee: number | null;
  target_calories: number | null;
  protein_g: number | null;
  carbs_g: number | null;
  fat_g: number | null;
}

export function ActivityLevelSelector({
  goal,
  onApply,
}: {
  goal: string;
  onApply?: (targets: ActivityTargets) => void;
}) {
  const [levels, setLevels] = useState<ActivityLevel[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [targets, setTargets] = useState<ActivityTargets | null>(null);
  const [calculating, setCalculating] = useState(false);

  useEffect(() => {
    api
      .get<{ levels: ActivityLevel[]; default: string }>("/activity-levels")
      .then((res) => {
        if (res?.levels) {
          setLevels(res.levels);
          setSelected(res.default);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!selected) return;
    setCalculating(true);
    api
      .post<ActivityTargets>("/activity-levels/calculate", {
        activity_level: selected,
        goal,
      })
      .then((res) => setTargets(res))
      .catch(() => setTargets(null))
      .finally(() => setCalculating(false));
  }, [selected, goal]);

  const macroRows = useMemo(
    () =>
      targets
        ? [
            { label: "蛋白质", value: targets.protein_g },
            { label: "碳水", value: targets.carbs_g },
            { label: "脂肪", value: targets.fat_g },
          ]
        : [],
    [targets],
  );

  return (
    <div className="rounded-xl border border-emerald-100 bg-emerald-50/40 p-3">
      <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-emerald-700">
        <Gauge className="size-3.5 text-emerald-500" />
        活动量档位换算
      </div>

      <div className="flex flex-wrap gap-1.5">
        {levels.map((lv) => (
          <button
            key={lv.value}
            type="button"
            onClick={() => setSelected(lv.value)}
            className={cn(
              "rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
              selected === lv.value
                ? "bg-emerald-600 text-white"
                : "bg-white text-emerald-700 hover:bg-emerald-100",
            )}
          >
            {lv.label}
          </button>
        ))}
      </div>

      {calculating ? (
        <div className="mt-3 flex items-center gap-2 text-xs text-emerald-600/70">
          <Loader2 className="size-3.5 animate-spin" />
          换算中…
        </div>
      ) : targets ? (
        <div className="mt-3 space-y-2">
          <div className="flex items-center justify-between rounded-lg bg-white/70 px-3 py-2">
            <span className="flex items-center gap-1.5 text-xs text-emerald-700">
              <Flame className="size-3.5 text-orange-500" />
              每日热量目标
            </span>
            <span className="text-sm font-bold tabular-nums text-emerald-950">
              {targets.target_calories != null ? `${targets.target_calories} kcal` : "数据不足"}
            </span>
          </div>
          {targets.target_calories != null && (
            <div className="grid grid-cols-3 gap-1.5">
              {macroRows.map((m) => (
                <div key={m.label} className="rounded-md bg-white/70 px-2 py-1.5 text-center">
                  <p className="text-[10px] text-emerald-600/70">{m.label}</p>
                  <p className="text-sm font-bold tabular-nums text-emerald-950">
                    {m.value}
                    <span className="ml-0.5 text-[10px] font-normal text-emerald-400">g</span>
                  </p>
                </div>
              ))}
            </div>
          )}
          <p className="text-[11px] text-emerald-600/60">
            基础代谢 {targets.bmr != null ? `${targets.bmr} kcal` : "--"} · 消耗{" "}
            {targets.tdee != null ? `${targets.tdee} kcal` : "--"}
          </p>
          {onApply && targets.target_calories != null && (
            <Button
              size="sm"
              className="h-7 text-xs"
              onClick={() => onApply(targets)}
            >
              应用为每日营养目标
            </Button>
          )}
        </div>
      ) : (
        <p className="mt-3 text-[11px] text-emerald-600/50">
          完善身高/体重/年龄后即可自动换算
        </p>
      )}
    </div>
  );
}
