/**
 * 动作详情页 /exercises/:id
 *
 * 动图 + 名称 + 全标签 + 描述 + 编号步骤 + 英文说明（折叠）+ 热量 + 署名。
 */
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Loader2,
  Flame,
  ChevronDown,
  ChevronUp,
  ImageIcon,
  Layers,
  Heart,
} from "lucide-react";
import { AppLayout } from "@/components/app-layout";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { api, exerciseFavApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/lib/language-context";
import {
  muscleGroupLabels,
  difficultyLabels,
  difficultyColors,
  categoryLabels,
  useLabel,
  exerciseDescription,
} from "@/lib/exercise-labels";
import type { Exercise } from "@/types/exercise";

export default function ExerciseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { isZh } = useLanguage();
  const label = useLabel();
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showEn, setShowEn] = useState(false);
  const [favorited, setFavorited] = useState(false);
  const [favLoading, setFavLoading] = useState(false);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setError("");
    api
      .get<Exercise>(`/exercises/${id}`)
      .then((ex) => {
        if (!cancelled) setExercise(ex);
      })
      .catch((e) => {
        if (!cancelled) setError((e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    exerciseFavApi.listIds().then((ids) => {
      if (!cancelled && id) setFavorited(ids.includes(id));
    }).catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [id]);

  const toggleFav = async () => {
    if (!id || favLoading) return;
    setFavLoading(true);
    try {
      const res = await exerciseFavApi.toggle(id);
      setFavorited(res.favorited);
    } catch { /* silent */ }
    finally { setFavLoading(false); }
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-4xl space-y-5 p-6">
          <div className="flex items-center gap-3">
            <Link
              to="/exercises"
              className={cn(
                buttonVariants({ variant: "ghost", size: "sm" }),
                "text-emerald-700",
              )}
            >
              <ArrowLeft className="size-4" />
              {isZh ? "返回动作库" : "Back to Exercises"}
            </Link>
          </div>

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          ) : exercise ? (
            <>
              <div className="grid gap-5 md:grid-cols-[280px_1fr]">
                {/* 媒体 */}
                <Card className="overflow-hidden border-emerald-100 bg-white/80">
                  <CardContent className="p-3">
                    <div className="relative aspect-square w-full overflow-hidden rounded-lg bg-emerald-50">
                      {exercise.gif_url || exercise.image ? (
                        <img
                          src={exercise.gif_url ?? exercise.image ?? ""}
                          alt={exercise.name}
                          className="absolute inset-0 size-full object-contain"
                        />
                      ) : (
                        <div className="flex size-full items-center justify-center text-emerald-200">
                          <ImageIcon className="size-10" />
                        </div>
                      )}
                    </div>
                    {exercise.calories_per_min != null && (
                      <p className="mt-2 flex items-center gap-1 text-sm text-orange-600">
                        <Flame className="size-4" />
                        {exercise.calories_per_min} {isZh ? "kcal/分钟" : "kcal/min"}
                      </p>
                    )}
                    {exercise.is_compound && (
                      <p className="mt-1 flex items-center gap-1 text-xs text-emerald-600">
                        <Layers className="size-3.5" />
                        {isZh ? "复合动作" : "Compound"}
                      </p>
                    )}
                  </CardContent>
                </Card>

                {/* 信息 */}
                <div className="space-y-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h1 className="text-2xl font-bold text-emerald-950">
                        {isZh ? exercise.name : (exercise.name_en || exercise.name)}
                      </h1>
                      {isZh
                        ? exercise.name_en && exercise.name_en !== exercise.name && (
                            <p className="text-sm text-emerald-500">{exercise.name_en}</p>
                          )
                        : exercise.name !== (exercise.name_en || exercise.name) && (
                            <p className="text-sm text-emerald-500">{exercise.name}</p>
                          )}
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={toggleFav}
                      disabled={favLoading}
                      className={cn(
                        "shrink-0 rounded-full transition-colors",
                        favorited
                          ? "text-rose-500 hover:bg-rose-50 hover:text-rose-600"
                          : "text-emerald-300 hover:bg-emerald-50 hover:text-rose-400"
                      )}
                      title={favorited ? (isZh ? "取消收藏" : "Unfavorite") : (isZh ? "收藏" : "Favorite")}
                    >
                      {favLoading ? (
                        <Loader2 className="size-5 animate-spin" />
                      ) : (
                        <Heart className={cn("size-5", favorited && "fill-current")} />
                      )}
                    </Button>
                  </div>

                  <div className="flex flex-wrap gap-1.5">
                    {exercise.muscle_group && (
                      <Badge variant="outline" className="border-emerald-200 text-emerald-600">
                        {label(muscleGroupLabels, exercise.muscle_group)}
                      </Badge>
                    )}
                    {(isZh ? exercise.body_part_zh : exercise.body_part) && (
                      <Badge variant="outline" className="border-emerald-200 text-emerald-600">
                        {isZh ? exercise.body_part_zh : exercise.body_part}
                      </Badge>
                    )}
                    {(isZh ? exercise.target_zh : exercise.target) && (
                      <Badge variant="outline" className="border-emerald-200 text-emerald-600">
                        {isZh ? "目标：" : "Target: "}{isZh ? exercise.target_zh : exercise.target}
                      </Badge>
                    )}
                    {(isZh ? exercise.equipment_zh : exercise.equipment) && (
                      <Badge variant="outline" className="border-sky-200 bg-sky-50 text-sky-600">
                        {isZh ? exercise.equipment_zh : exercise.equipment}
                      </Badge>
                    )}
                    {exercise.difficulty && (
                      <Badge variant="outline" className={difficultyColors[exercise.difficulty] ?? ""}>
                        {label(difficultyLabels, exercise.difficulty)}
                      </Badge>
                    )}
                    {exercise.category && (
                      <Badge variant="outline" className="border-emerald-200 text-emerald-600">
                        {label(categoryLabels, exercise.category)}
                      </Badge>
                    )}
                  </div>

                  {(() => {
                    const secMuscles = isZh ? exercise.secondary_muscles_zh : exercise.secondary_muscles;
                    if (!secMuscles || secMuscles.length === 0) return null;
                    return (
                      <div>
                        <p className="mb-1 text-xs font-medium text-emerald-700">
                          {isZh ? "协同肌群" : "Secondary Muscles"}
                        </p>
                        <div className="flex flex-wrap gap-1.5">
                          {secMuscles.map((m) => (
                            <Badge
                              key={m}
                              variant="secondary"
                              className="border-emerald-100 bg-emerald-50 text-emerald-700"
                            >
                              {m}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    );
                  })()}

                  {exerciseDescription(exercise, isZh) && (
                    <div className="rounded-lg border border-emerald-100 bg-emerald-50/40 p-3">
                      <p className="text-xs font-medium text-emerald-700">
                        {isZh ? "摘要" : "Summary"}
                      </p>
                      <p className="mt-1 text-sm text-emerald-800">
                        {exerciseDescription(exercise, isZh)}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* 步骤 */}
              {(() => {
                const steps = isZh ? exercise.instruction_steps : exercise.instruction_steps_en;
                if (!steps || steps.length === 0) return null;
                return (
                  <Card className="border-emerald-100 bg-white/80">
                    <CardContent className="p-4">
                      <h2 className="mb-3 text-sm font-semibold text-emerald-800">
                        {isZh ? "动作步骤" : "Steps"}
                      </h2>
                      <ol className="space-y-2">
                        {steps.map((step, idx) => (
                          <li key={idx} className="flex gap-3">
                            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-emerald-700">
                              {idx + 1}
                            </span>
                            <p className="pt-0.5 text-sm text-emerald-800">{step}</p>
                          </li>
                        ))}
                      </ol>
                    </CardContent>
                  </Card>
                );
              })()}

              {/* 完整说明：中文模式显示 instructions，英文模式优先 instructions_en */}
              {(isZh ? exercise.instructions : (exercise.instructions_en || exercise.instructions)) && (
                <Card className="border-emerald-100 bg-white/80">
                  <CardContent className="p-4">
                    <h2 className="mb-2 text-sm font-semibold text-emerald-800">
                      {isZh ? "完整说明" : "Full Instructions"}
                    </h2>
                    <p className="whitespace-pre-line text-sm text-emerald-800">
                      {isZh ? exercise.instructions : (exercise.instructions_en || exercise.instructions)}
                    </p>
                  </CardContent>
                </Card>
              )}

              {/* 另一语言说明（折叠） */}
              {(isZh ? exercise.instructions_en : exercise.instructions) && (
                <Card className="border-emerald-100 bg-white/80">
                  <CardContent className="p-4">
                    <button
                      type="button"
                      onClick={() => setShowEn((v) => !v)}
                      className="flex w-full items-center justify-between text-sm font-semibold text-emerald-800"
                    >
                      <span>{isZh ? "English Instructions" : "中文说明"}</span>
                      {showEn ? (
                        <ChevronUp className="size-4 text-emerald-500" />
                      ) : (
                        <ChevronDown className="size-4 text-emerald-500" />
                      )}
                    </button>
                    {showEn && (
                      <p className="mt-3 whitespace-pre-line text-sm text-emerald-700/80">
                        {isZh ? exercise.instructions_en : exercise.instructions}
                      </p>
                    )}
                  </CardContent>
                </Card>
              )}

              <footer className="border-t border-emerald-100 pt-4 text-center text-xs text-emerald-500/70">
                {isZh ? "动作图片与动图" : "Exercise images & GIFs"} {exercise.attribution ?? "© Gym visual - https://gymvisual.com/"}
              </footer>
            </>
          ) : null}
        </div>
      </div>
    </AppLayout>
  );
}
