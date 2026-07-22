import { useEffect, useState } from "react";
import { AppLayout } from "@/components/app-layout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  CalendarCheck,
  Loader2,
  Flame,
  Trophy,
  Plus,
  Clock,
  Smile,
  StickyNote,
} from "lucide-react";
import { api } from "@/lib/api";

interface CheckinExercise {
  id: string;
  exercise_name: string | null;
  sets_done: number | null;
  reps_done: number | null;
  weight_kg: number | null;
}

interface Checkin {
  id: string;
  date: string;
  duration_min: number;
  mood: number | null;
  note: string | null;
  exercises: CheckinExercise[];
}

interface Streak {
  current_streak: number;
  longest_streak: number;
  last_checkin_date: string | null;
}

const moodEmojis = ["😫", "😕", "😐", "🙂", "🤩"];

export default function CheckinsPage() {
  const [checkins, setCheckins] = useState<Checkin[]>([]);
  const [streak, setStreak] = useState<Streak | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [open, setOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    duration_min: "30",
    mood: "4",
    note: "",
  });

  const loadData = async () => {
    try {
      const [checkinRes, streakRes] = await Promise.all([
        api.get<{ items: Checkin[] }>("/checkins"),
        api.get<Streak>("/checkins/streak"),
      ]);
      setCheckins(checkinRes.items || []);
      setStreak(streakRes);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleCreate = async () => {
    setSaving(true);
    setError("");
    try {
      await api.post("/checkins", {
        date: form.date,
        duration_min: Number(form.duration_min) || 30,
        mood: form.mood ? Number(form.mood) : null,
        note: form.note || null,
        exercises: [],
      });
      setOpen(false);
      setForm({
        date: new Date().toISOString().slice(0, 10),
        duration_min: "30",
        mood: "4",
        note: "",
      });
      await loadData();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <AppLayout>
      <div className="h-full overflow-y-auto">
        <div className="mx-auto max-w-4xl space-y-6 p-6">
          <header className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex size-11 items-center justify-center rounded-2xl bg-emerald-100">
                <CalendarCheck className="size-5 text-emerald-600" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-emerald-950">打卡记录</h1>
                <p className="text-sm text-emerald-600/60">记录每一次训练，见证坚持的力量</p>
              </div>
            </div>
            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger
                render={
                  <Button className="bg-emerald-600 text-white hover:bg-emerald-500" />
                }
              >
                <Plus className="mr-2 size-4" />
                打卡
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle className="text-emerald-950">新增打卡</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 pt-2">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-emerald-800">日期</label>
                    <Input
                      type="date"
                      value={form.date}
                      onChange={(e) => setForm({ ...form, date: e.target.value })}
                      className="border-emerald-200 focus-visible:ring-emerald-400"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-emerald-800">训练时长（分钟）</label>
                    <Input
                      type="number"
                      value={form.duration_min}
                      onChange={(e) => setForm({ ...form, duration_min: e.target.value })}
                      className="border-emerald-200 focus-visible:ring-emerald-400"
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-emerald-800">心情评分</label>
                    <div className="flex gap-2">
                      {moodEmojis.map((emoji, i) => (
                        <button
                          key={i}
                          onClick={() => setForm({ ...form, mood: String(i + 1) })}
                          className={`flex size-10 items-center justify-center rounded-lg border text-xl transition-all ${
                            form.mood === String(i + 1)
                              ? "border-emerald-400 bg-emerald-50 ring-1 ring-emerald-300"
                              : "border-emerald-100 hover:border-emerald-200"
                          }`}
                        >
                          {emoji}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-emerald-800">备注</label>
                    <Textarea
                      value={form.note}
                      onChange={(e) => setForm({ ...form, note: e.target.value })}
                      placeholder="今天的训练感受..."
                      className="border-emerald-200 focus-visible:ring-emerald-400"
                    />
                  </div>
                  {error && <p className="text-sm text-red-500">{error}</p>}
                  <Button
                    onClick={handleCreate}
                    disabled={saving}
                    className="w-full bg-emerald-600 text-white hover:bg-emerald-500"
                  >
                    {saving && <Loader2 className="mr-2 size-4 animate-spin" />}
                    确认打卡
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          </header>

          {/* 连续打卡统计 */}
          {streak && (
            <div className="grid gap-4 sm:grid-cols-3">
              <Card className="border-orange-100 bg-gradient-to-br from-orange-50 to-amber-50/60">
                <CardContent className="flex items-center gap-3 p-5">
                  <div className="flex size-10 items-center justify-center rounded-xl bg-orange-100">
                    <Flame className="size-5 text-orange-500" />
                  </div>
                  <div>
                    <p className="text-xs text-orange-600/60">当前连续</p>
                    <p className="text-2xl font-bold text-orange-600">
                      {streak.current_streak}
                      <span className="ml-1 text-sm font-normal">天</span>
                    </p>
                  </div>
                </CardContent>
              </Card>
              <Card className="border-amber-100 bg-gradient-to-br from-amber-50 to-yellow-50/60">
                <CardContent className="flex items-center gap-3 p-5">
                  <div className="flex size-10 items-center justify-center rounded-xl bg-amber-100">
                    <Trophy className="size-5 text-amber-500" />
                  </div>
                  <div>
                    <p className="text-xs text-amber-600/60">最长连续</p>
                    <p className="text-2xl font-bold text-amber-600">
                      {streak.longest_streak}
                      <span className="ml-1 text-sm font-normal">天</span>
                    </p>
                  </div>
                </CardContent>
              </Card>
              <Card className="border-emerald-100 bg-gradient-to-br from-emerald-50 to-teal-50/60">
                <CardContent className="flex items-center gap-3 p-5">
                  <div className="flex size-10 items-center justify-center rounded-xl bg-emerald-100">
                    <CalendarCheck className="size-5 text-emerald-500" />
                  </div>
                  <div>
                    <p className="text-xs text-emerald-600/60">上次打卡</p>
                    <p className="text-lg font-bold text-emerald-700">
                      {streak.last_checkin_date ?? "暂无"}
                    </p>
                  </div>
                </CardContent>
              </Card>
            </div>
          )}

          {error && (
            <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-600">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-20 text-emerald-500">
              <Loader2 className="size-6 animate-spin" />
            </div>
          ) : checkins.length === 0 ? (
            <Card className="border-dashed border-emerald-200">
              <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
                <CalendarCheck className="size-8 text-emerald-300" />
                <p className="text-sm text-emerald-600/60">还没有打卡记录，点击右上角开始第一次打卡吧</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {checkins.map((c) => (
                <Card key={c.id} className="border-emerald-100 bg-white/80 shadow-sm backdrop-blur">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2 text-base font-semibold text-emerald-950">
                        <CalendarCheck className="size-4 text-emerald-500" />
                        {c.date}
                      </CardTitle>
                      <div className="flex items-center gap-3 text-sm text-emerald-600/70">
                        <span className="flex items-center gap-1">
                          <Clock className="size-3.5" />
                          {c.duration_min} 分钟
                        </span>
                        {c.mood && (
                          <span className="flex items-center gap-1">
                            <Smile className="size-3.5" />
                            {moodEmojis[c.mood - 1]}
                          </span>
                        )}
                      </div>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    {c.exercises.length > 0 && (
                      <div className="space-y-1.5">
                        {c.exercises.map((ex) => (
                          <div
                            key={ex.id}
                            className="flex items-center justify-between rounded-lg bg-emerald-50/60 px-3 py-2 text-sm"
                          >
                            <span className="font-medium text-emerald-900">
                              {ex.exercise_name ?? "未知动作"}
                            </span>
                            <span className="tabular-nums text-emerald-600/70">
                              {ex.sets_done ?? "-"} 组 × {ex.reps_done ?? "-"} 次
                              {ex.weight_kg ? ` · ${ex.weight_kg}kg` : ""}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                    {c.note && (
                      <div className="flex items-start gap-2 rounded-lg bg-emerald-50/40 px-3 py-2 text-sm text-emerald-700">
                        <StickyNote className="mt-0.5 size-3.5 shrink-0 text-emerald-400" />
                        <span>{c.note}</span>
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}