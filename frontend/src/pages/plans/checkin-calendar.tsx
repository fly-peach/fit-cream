import { useMemo, useState } from "react";
import {
  format,
  startOfMonth,
  endOfMonth,
  eachDayOfInterval,
  isSameMonth,
  isSameDay,
  addMonths,
  subMonths,
  startOfWeek,
  endOfWeek,
  isToday,
} from "date-fns";
import { zhCN } from "date-fns/locale";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Dumbbell,
  CalendarDays,
  ChevronRight,
  ChevronLeft,
  ChevronDown,
  ChevronUp,
  Flame,
  UtensilsCrossed,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { CalMode } from "./types";

export function CheckinCalendar({
  mode,
  onModeChange,
  selectedDate,
  onPickDate,
  checkinDates,
  streak,
  dietDayCalories,
  dietTargetCalories,
}: {
  mode: CalMode;
  onModeChange: (m: CalMode) => void;
  selectedDate: Date;
  onPickDate: (d: Date) => void;
  checkinDates: Set<string>;
  streak: number;
  dietDayCalories: number;
  dietTargetCalories: number | null;
}) {
  const [currentMonth, setCurrentMonth] = useState(selectedDate);
  const [syncMode, setSyncMode] = useState(mode);
  const [collapsed, setCollapsed] = useState(false);

  if (mode !== syncMode) {
    setSyncMode(mode);
    setCurrentMonth(selectedDate);
  }

  const calendarDays = useMemo(() => {
    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calStart = startOfWeek(monthStart, { weekStartsOn: 1 });
    const calEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
    return eachDayOfInterval({ start: calStart, end: calEnd });
  }, [currentMonth]);

  const monthCheckins = useMemo(() => {
    return calendarDays.filter(
      (d) => isSameMonth(d, currentMonth) && checkinDates.has(format(d, "yyyy-MM-dd")),
    ).length;
  }, [calendarDays, currentMonth, checkinDates]);

  const selectedChecked = checkinDates.has(format(selectedDate, "yyyy-MM-dd"));
  const isExercise = mode === "exercise";

  return (
    <Card className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-emerald-950">
            <CalendarDays className="size-4 text-emerald-500" />
            {isExercise ? "锻炼日历" : "饮食日历"}
          </CardTitle>
          <div className="flex items-center gap-1">
            <div className="hidden items-center gap-1 rounded-lg bg-emerald-50 p-0.5 lg:flex">
              <button
                type="button"
                onClick={() => onModeChange("exercise")}
                className={cn(
                  "flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  isExercise
                    ? "bg-white text-emerald-700 shadow-sm"
                    : "text-emerald-600/60 hover:text-emerald-700",
                )}
              >
                <Dumbbell className="size-3.5" />
                锻炼
              </button>
              <button
                type="button"
                onClick={() => onModeChange("diet")}
                className={cn(
                  "flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium transition-colors",
                  !isExercise
                    ? "bg-white text-orange-700 shadow-sm"
                    : "text-orange-600/60 hover:text-orange-700",
                )}
              >
                <UtensilsCrossed className="size-3.5" />
                饮食
              </button>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="size-7 text-emerald-600/70"
              onClick={() => setCollapsed((v) => !v)}
              title={collapsed ? "展开" : "折叠"}
            >
              {collapsed ? <ChevronDown className="size-4" /> : <ChevronUp className="size-4" />}
            </Button>
          </div>
        </div>
        {!collapsed && (
          <div className="flex items-center justify-between">
            <span className="text-xs text-emerald-600/70">
              选中 {format(selectedDate, "yyyy年M月d日", { locale: zhCN })}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                className="size-7 text-emerald-700 hover:bg-emerald-100"
                onClick={() => setCurrentMonth(subMonths(currentMonth, 1))}
              >
                <ChevronLeft className="size-4" />
              </Button>
              <span className="min-w-20 text-center text-sm font-medium text-emerald-900">
                {format(currentMonth, "yyyy年M月", { locale: zhCN })}
              </span>
              <Button
                variant="ghost"
                size="icon"
                className="size-7 text-emerald-700 hover:bg-emerald-100"
                onClick={() => setCurrentMonth(addMonths(currentMonth, 1))}
              >
                <ChevronRight className="size-4" />
              </Button>
            </div>
          </div>
        )}
      </CardHeader>
      {!collapsed && (
        <CardContent>
        <div className="mb-2 grid grid-cols-7 text-center text-xs font-medium text-emerald-600/60">
          {["一", "二", "三", "四", "五", "六", "日"].map((d) => (
            <div key={d} className="py-1">
              {d}
            </div>
          ))}
        </div>
        <div className="grid grid-cols-7 gap-1">
          {calendarDays.map((day) => {
            const dateStr = format(day, "yyyy-MM-dd");
            const checked = checkinDates.has(dateStr);
            const inMonth = isSameMonth(day, currentMonth);
            const isSelected = isSameDay(day, selectedDate);

            return (
              <button
                key={dateStr}
                onClick={() => onPickDate(day)}
                className={cn(
                  "relative flex size-9 items-center justify-center rounded-lg text-sm transition-all duration-150",
                  !inMonth && "text-emerald-200",
                  inMonth && !isSelected && "text-emerald-800 hover:bg-emerald-50",
                  isExercise && checked && "bg-emerald-100 font-medium text-emerald-700 hover:bg-emerald-200",
                  isSelected && (isExercise ? "ring-2 ring-emerald-400" : "ring-2 ring-orange-400"),
                  isToday(day) && "font-bold text-emerald-950",
                )}
              >
                {format(day, "d")}
                {isExercise && checked && (
                  <span className="absolute bottom-1 size-1 rounded-full bg-emerald-500" />
                )}
              </button>
            );
          })}
        </div>
        <div className="mt-4 space-y-2">
          {isExercise ? (
            <>
              <div className="flex items-center justify-between rounded-lg bg-emerald-50 px-3 py-2">
                <span className="text-xs text-emerald-700">
                  {format(selectedDate, "M月d日", { locale: zhCN })}
                  {selectedChecked ? (
                    <span className="ml-2 font-medium text-emerald-600">✓ 已打卡</span>
                  ) : (
                    <span className="ml-2 text-emerald-400">未打卡</span>
                  )}
                </span>
                <span className="text-xs text-emerald-700">
                  本月 <span className="font-semibold text-emerald-600">{monthCheckins}</span> 天
                </span>
              </div>
              <div className="flex items-center justify-between rounded-lg bg-orange-50 px-3 py-2">
                <span className="flex items-center gap-1.5 text-xs text-orange-600">
                  <Flame className="size-3.5 text-orange-500" />
                  当前连续打卡
                </span>
                <span className="text-sm font-bold text-orange-600">
                  {streak}
                  <span className="ml-0.5 text-xs font-normal">天</span>
                </span>
              </div>
            </>
          ) : (
            <div className="flex items-center justify-between rounded-lg bg-orange-50 px-3 py-2">
              <span className="flex items-center gap-1.5 text-xs text-orange-600">
                <Flame className="size-3.5 text-orange-500" />
                当日热量
              </span>
              <span className="text-sm font-bold text-orange-600">
                {dietDayCalories}
                <span className="ml-0.5 text-xs font-normal">
                  kcal{dietTargetCalories ? ` / ${dietTargetCalories}` : ""}
                </span>
              </span>
            </div>
          )}
        </div>
      </CardContent>
      )}
    </Card>
  );
}
