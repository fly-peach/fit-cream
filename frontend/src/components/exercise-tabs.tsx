/**
 * 动作库页内 tab：动作库（exercise-database）/ 动作组（exercise-group）
 *
 * 两个页面共用；以当前路径判定高亮，点击跳转对应路由。
 */
import { NavLink } from "react-router-dom";
import { Dumbbell, Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import { useLanguage } from "@/lib/language-context";

const tabs = [
  { to: "/exercises/exercise-database", zh: "动作库", en: "Exercises", icon: Dumbbell },
  { to: "/exercises/exercise-group", zh: "动作组", en: "Groups", icon: Layers },
];

export function ExerciseTabs() {
  const { isZh } = useLanguage();
  return (
    <div className="flex items-center gap-1 rounded-xl border border-emerald-100 bg-white/60 p-1">
      {tabs.map((t) => (
        <NavLink
          key={t.to}
          to={t.to}
          className={({ isActive }) =>
            cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-semibold transition-all",
              isActive
                ? "bg-emerald-500 text-white shadow-sm shadow-emerald-500/30"
                : "text-emerald-600/60 hover:bg-emerald-50 hover:text-emerald-700",
            )
          }
        >
          <t.icon className="size-3.5" />
          {isZh ? t.zh : t.en}
        </NavLink>
      ))}
    </div>
  );
}
