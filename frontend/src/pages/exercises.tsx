/**
 * 动作库列表页 /exercises
 *
 * 搜索 + 筛选（muscle_group/body_part/equipment/difficulty/target）+ 卡片网格
 * （缩略图 hover 切换动图 GIF）+ 加载更多；点击卡片跳转 /exercises/:id。
 * 页脚保留 © Gym visual 媒体署名。
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Loader2,
  Search,
  Flame,
  Dumbbell,
  X,
  ImageIcon,
  SlidersHorizontal,
  Layers,
  PersonStanding,
  Wrench,
  Gauge,
  Crosshair,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/lib/language-context";
import {
  muscleGroupLabels,
  bodyPartLabels,
  equipmentLabels,
  difficultyLabels,
  difficultyColors,
  targetLabels,
  useLabel,
  formatEnLabel,
} from "@/lib/exercise-labels";
import type {
  EquipmentStats,
  Exercise,
  MuscleGroupStats,
} from "@/types/exercise";

const PAGE_SIZE = 24;

interface FilterOption {
  value: string;
  label: string;
}

function FilterSelect({
  value,
  onChange,
  options,
  placeholder,
  icon: Icon,
  label,
}: {
  value: string;
  onChange: (v: string) => void;
  options: FilterOption[];
  placeholder: string;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
}) {
  const isActive = !!value;
  const selectedLabel = options.find((o) => o.value === value)?.label;

  return (
    <div
      className={cn(
        "group/filter relative overflow-hidden rounded-xl border transition-all duration-200",
        isActive
          ? "border-emerald-300 bg-emerald-50/80 shadow-sm shadow-emerald-100/50"
          : "border-emerald-100 bg-white/60 hover:border-emerald-200 hover:bg-white/80"
      )}
    >
      <div
        className={cn(
          "absolute inset-y-0 left-0 w-[3px] rounded-r-full transition-all duration-200",
          isActive ? "bg-emerald-500" : "bg-transparent"
        )}
      />
      <Select value={value || undefined} onValueChange={(v) => onChange(v ?? "")}>
        <SelectTrigger className="h-auto min-w-0 border-0 bg-transparent px-3 py-2 shadow-none ring-0 focus-visible:ring-0">
          <SelectValue placeholder={placeholder}>
            <span className="flex min-w-0 items-center gap-2">
              <Icon
                className={cn(
                  "size-3.5 shrink-0 transition-colors duration-200",
                  isActive ? "text-emerald-600" : "text-emerald-400/60"
                )}
              />
              <span className="shrink-0 text-[11px] font-medium text-emerald-500/70">
                {label}
              </span>
              <span
                className={cn(
                  "truncate text-xs font-medium",
                  isActive ? "text-emerald-700" : "text-emerald-400/80"
                )}
              >
                {selectedLabel ?? placeholder}
              </span>
            </span>
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          {options.map((o) => (
            <SelectItem key={o.value} value={o.value}>
              {o.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function ExerciseCard({ ex }: { ex: Exercise }) {
  const navigate = useNavigate();
  const { isZh } = useLanguage();
  const label = useLabel();
  const primaryName = isZh ? ex.name : (ex.name_en || ex.name);
  const secondaryName = isZh ? ex.name_en : ex.name;
  return (
    <Card
      onClick={() => navigate(`/exercises/${ex.id}`)}
      className="group cursor-pointer overflow-hidden border-emerald-100 bg-white/80 transition-all hover:border-emerald-300 hover:shadow-md"
    >
      <CardContent className="flex flex-col gap-2 p-3">
        {/* 媒体：缩略图，hover 切换 GIF */}
        <div className="relative aspect-square w-full overflow-hidden rounded-lg bg-emerald-50">
          {ex.image || ex.gif_url ? (
            <>
              {ex.image && (
                <img
                  src={ex.image}
                  alt={ex.name}
                  loading="lazy"
                  className="absolute inset-0 size-full object-contain transition-opacity duration-200 group-hover:opacity-0"
                />
              )}
              {ex.gif_url && (
                <img
                  src={ex.gif_url}
                  alt={ex.name}
                  loading="lazy"
                  className="absolute inset-0 size-full object-contain opacity-0 transition-opacity duration-200 group-hover:opacity-100"
                />
              )}
            </>
          ) : (
            <div className="flex size-full items-center justify-center text-emerald-200">
              <ImageIcon className="size-8" />
            </div>
          )}
        </div>

        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-emerald-950">
            {primaryName}
          </h3>
          {secondaryName && secondaryName !== primaryName && (
            <p className="truncate text-xs text-emerald-500">{secondaryName}</p>
          )}
        </div>

        <div className="flex flex-wrap gap-1.5">
          {ex.muscle_group && (
            <Badge variant="outline" className="border-emerald-200 text-emerald-600">
              {label(muscleGroupLabels, ex.muscle_group)}
            </Badge>
          )}
          {(isZh ? ex.equipment_zh : ex.equipment) && (
            <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-600">
              {isZh ? ex.equipment_zh : formatEnLabel(ex.equipment ?? "")}
            </Badge>
          )}
          {ex.difficulty && (
            <Badge variant="outline" className={difficultyColors[ex.difficulty] ?? ""}>
              {label(difficultyLabels, ex.difficulty)}
            </Badge>
          )}
        </div>

        {ex.description && (
          <p className="line-clamp-2 text-xs text-emerald-700/70">{ex.description}</p>
        )}
        {ex.calories_per_min != null && (
          <p className="flex items-center gap-1 text-xs text-orange-600/80">
            <Flame className="size-3" />
            {ex.calories_per_min} kcal/分钟
          </p>
        )}
      </CardContent>
    </Card>
  );
}

export default function ExercisesPage() {
  const { isZh } = useLanguage();
  const label = useLabel();
  const [items, setItems] = useState<Exercise[]>([]);
  const [keywordInput, setKeywordInput] = useState("");
  const [keyword, setKeyword] = useState("");
  const [muscleGroup, setMuscleGroup] = useState("");
  const [bodyPart, setBodyPart] = useState("");
  const [equipment, setEquipment] = useState("");
  const [difficulty, setDifficulty] = useState("");
  const [target, setTarget] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [error, setError] = useState("");
  const [muscleGroups, setMuscleGroups] = useState<MuscleGroupStats[]>([]);
  const [equipments, setEquipments] = useState<EquipmentStats[]>([]);

  // 拉取筛选可选项（含计数，equipment 取动态值）
  useEffect(() => {
    Promise.all([
      api.get<MuscleGroupStats[]>("/exercises/muscle-groups").catch(() => []),
      api.get<EquipmentStats[]>("/exercises/equipments").catch(() => []),
    ]).then(([mg, eq]) => {
      setMuscleGroups(mg ?? []);
      setEquipments(eq ?? []);
    });
  }, []);

  const allOption: FilterOption = { value: "", label: isZh ? "全部" : "All" };
  const difficultyOptions: FilterOption[] = [
    allOption,
    ...Object.entries(difficultyLabels).map(([value]) => ({
      value,
      label: label(difficultyLabels, value) ?? value,
    })),
  ];
  const muscleGroupOptions: FilterOption[] = [
    allOption,
    ...muscleGroups.map((m) => ({
      value: m.name,
      label: `${label(muscleGroupLabels, m.name)} (${m.count})`,
    })),
  ];
  const bodyPartOptions: FilterOption[] = [
    allOption,
    ...Object.entries(bodyPartLabels).map(([value]) => ({
      value,
      label: label(bodyPartLabels, value) ?? value,
    })),
  ];
  const equipmentOptions: FilterOption[] = [
    allOption,
    ...equipments.map((e) => ({
      value: e.name,
      label: `${label(equipmentLabels, e.name)} (${e.count})`,
    })),
  ];
  const targetOptions: FilterOption[] = [
    allOption,
    ...Object.entries(targetLabels).map(([value]) => ({
      value,
      label: label(targetLabels, value) ?? value,
    })),
  ];

  // 过滤条件变化时重新加载第一页
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError("");

    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: "0" });
    if (keyword) params.set("keyword", keyword);
    if (muscleGroup) params.set("muscle_group", muscleGroup);
    if (bodyPart) params.set("body_part", bodyPart);
    if (equipment) params.set("equipment", equipment);
    if (difficulty) params.set("difficulty", difficulty);
    if (target) params.set("target", target);

    api
      .get<Exercise[]>(`/exercises?${params.toString()}`)
      .then((list) => {
        if (cancelled) return;
        setItems(list ?? []);
        setHasMore((list?.length ?? 0) >= PAGE_SIZE);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [keyword, muscleGroup, bodyPart, equipment, difficulty, target]);

  const loadMore = async () => {
    setLoadingMore(true);
    const params = new URLSearchParams({
      limit: String(PAGE_SIZE),
      offset: String(items.length),
    });
    if (keyword) params.set("keyword", keyword);
    if (muscleGroup) params.set("muscle_group", muscleGroup);
    if (bodyPart) params.set("body_part", bodyPart);
    if (equipment) params.set("equipment", equipment);
    if (difficulty) params.set("difficulty", difficulty);
    if (target) params.set("target", target);

    try {
      const list = await api.get<Exercise[]>(`/exercises?${params.toString()}`);
      setItems((prev) => [...prev, ...(list ?? [])]);
      setHasMore((list?.length ?? 0) >= PAGE_SIZE);
    } catch {
      // 静默：分页失败不阻塞
    } finally {
      setLoadingMore(false);
    }
  };

  const resetFilters = () => {
    setKeywordInput("");
    setKeyword("");
    setMuscleGroup("");
    setBodyPart("");
    setEquipment("");
    setDifficulty("");
    setTarget("");
  };

  const hasActiveFilter =
    !!keyword ||
    !!muscleGroup ||
    !!bodyPart ||
    !!equipment ||
    !!difficulty ||
    !!target;

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-7xl space-y-5 p-6">
          <header className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-100">
              <Dumbbell className="size-5 text-emerald-600" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-emerald-950">动作库</h1>
              <p className="text-sm text-emerald-600/60">
                1324 个动作 · 搜索/筛选并查看动图演示
              </p>
            </div>
          </header>

          {/* 搜索栏 */}
          <div className="flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-emerald-400" />
              <Input
                value={keywordInput}
                onChange={(e) => setKeywordInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    setKeyword(keywordInput.trim());
                  }
                }}
                placeholder="搜索动作名称或说明（如 深蹲 / squat）"
                className="rounded-xl border-emerald-200 bg-white/70 pl-9"
              />
            </div>
            <Button
              size="sm"
              variant="outline"
              className="border-emerald-200 text-emerald-700"
              onClick={() => setKeyword(keywordInput.trim())}
            >
              搜索
            </Button>
            {hasActiveFilter && (
              <Button
                size="sm"
                variant="ghost"
                className="text-emerald-600/70"
                onClick={resetFilters}
              >
                <X className="size-4" />
                重置
              </Button>
            )}
          </div>

          {/* 筛选器 */}
          <div className="rounded-2xl border border-emerald-100/80 bg-gradient-to-br from-emerald-50/40 to-white/60 p-3">
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-600/70">
                <SlidersHorizontal className="size-3.5" />
                筛选条件
              </span>
              {hasActiveFilter && (
                <button
                  onClick={resetFilters}
                  className="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-emerald-500/70 transition-colors hover:bg-emerald-100/50 hover:text-emerald-700"
                >
                  <X className="size-3" />
                  清除
                </button>
              )}
            </div>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
              <FilterSelect
                value={muscleGroup}
                onChange={setMuscleGroup}
                options={muscleGroupOptions}
                placeholder="肌群"
                icon={Layers}
                label="肌群"
              />
              <FilterSelect
                value={bodyPart}
                onChange={setBodyPart}
                options={bodyPartOptions}
                placeholder="部位"
                icon={PersonStanding}
                label="部位"
              />
              <FilterSelect
                value={equipment}
                onChange={setEquipment}
                options={equipmentOptions}
                placeholder="器械"
                icon={Wrench}
                label="器械"
              />
              <FilterSelect
                value={difficulty}
                onChange={setDifficulty}
                options={difficultyOptions}
                placeholder="难度"
                icon={Gauge}
                label="难度"
              />
              <FilterSelect
                value={target}
                onChange={setTarget}
                options={targetOptions}
                placeholder="目标肌"
                icon={Crosshair}
                label="目标"
              />
            </div>
          </div>

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : items.length === 0 ? (
            <div className="flex flex-col items-center gap-2 py-16 text-center text-emerald-600/50">
              <Dumbbell className="size-8 text-emerald-300" />
              <p className="text-sm">
                {hasActiveFilter ? "没有匹配的动作，试试调整筛选条件" : "暂无动作"}
              </p>
            </div>
          ) : (
            <>
              <p className="text-xs text-emerald-600/60">
                共 {items.length} 个动作，点击卡片查看详情
              </p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
                {items.map((ex) => (
                  <ExerciseCard key={ex.id} ex={ex} />
                ))}
              </div>

              {hasMore && (
                <div className="flex justify-center pt-2">
                  <Button
                    variant="outline"
                    className="border-emerald-200 text-emerald-700"
                    onClick={loadMore}
                    disabled={loadingMore}
                  >
                    {loadingMore ? (
                      <>
                        <Loader2 className="size-4 animate-spin" />
                        加载中...
                      </>
                    ) : (
                      "加载更多"
                    )}
                  </Button>
                </div>
              )}
            </>
          )}

          {/* 媒体署名（© Gym visual 许可要求） */}
          <footer className="border-t border-emerald-100 pt-4 text-center text-xs text-emerald-500/70">
            动作图片与动图 © Gym visual - https://gymvisual.com/
          </footer>
        </div>
      </div>
    </AppLayout>
  );
}
