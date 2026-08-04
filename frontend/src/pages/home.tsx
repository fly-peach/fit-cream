import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { useAuthStore } from "@/stores/auth-store";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";
import {
  SparklesIcon,
  MessageSquareIcon,
  CalendarCheckIcon,
  AppleIcon,
  BarChart3Icon,
  DumbbellIcon,
  BookOpenIcon,
  ArrowRightIcon,
  FlameIcon,
  ShieldCheckIcon,
  HeartPulseIcon,
  TrophyIcon,
  BotIcon,
  PaperclipIcon,
  MenuIcon,
  XIcon,
  ChevronRightIcon,
  TargetIcon,
  CalendarDaysIcon,
  ClipboardListIcon,
  SparkleIcon,
  GithubIcon,
} from "lucide-react";

/** 首页专用的独立动效（仅作用于本页元素，不影响其他路由） */
const HOME_STYLE = `
  @keyframes home-stream-dot {
    0%, 80%, 100% { transform: translateY(0); opacity: 0.4; }
    40% { transform: translateY(-4px); opacity: 1; }
  }
  @keyframes home-float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-10px); }
  }
  .home-float { animation: home-float 5s ease-in-out infinite; }
  @keyframes home-shimmer {
    0% { background-position: -200% 0; }
    100% { background-position: 200% 0; }
  }
  .home-shimmer {
    background: linear-gradient(
      90deg,
      rgba(110, 231, 183, 0.08) 25%,
      rgba(110, 231, 183, 0.35) 50%,
      rgba(110, 231, 183, 0.08) 75%
    );
    background-size: 200% 100%;
    animation: home-shimmer 2.2s linear infinite;
  }
  .home-dot { animation: home-stream-dot 1.2s ease-in-out infinite; }
  @media (prefers-reduced-motion: reduce) {
    .home-shimmer, .home-dot, .home-float { animation: none; }
  }
`;

const fadeUp: React.ComponentProps<typeof motion.div>["variants"] = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { duration: 0.6, ease: [0.22, 1, 0.36, 1] } },
};

const stagger: React.ComponentProps<typeof motion.div>["variants"] = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12 } },
};

/* ------------------------------ 顶栏 ------------------------------ */

function HomeNav({
  scrolled,
  open,
  onToggle,
  isAuthenticated,
}: {
  scrolled: boolean;
  open: boolean;
  onToggle: () => void;
  isAuthenticated: boolean;
}) {
  return (
    <motion.header
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled
          ? "border-b border-emerald-100/60 bg-white/80 backdrop-blur-xl"
          : "bg-transparent",
      )}
    >
      <nav className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <a href="#top" className="flex items-center gap-2.5">
          <Logo className="size-9 rounded-xl shadow-md shadow-emerald-500/25" />
          <span
            className={cn(
              "font-display text-xl font-bold tracking-tight transition-colors",
              scrolled ? "text-emerald-950" : "text-white",
            )}
          >
            Fit<span className={scrolled ? "text-emerald-500" : "text-emerald-400"}>Cream</span>
          </span>
        </a>

        {/* 桌面导航 */}
        <div className="hidden items-center gap-7 md:flex">
          <a
            href="#features"
            className={cn(
              "text-sm font-medium transition-colors",
              scrolled ? "text-emerald-800/70 hover:text-emerald-600" : "text-emerald-100/70 hover:text-white",
            )}
          >
            功能特性
          </a>
          <a
            href="#how"
            className={cn(
              "text-sm font-medium transition-colors",
              scrolled ? "text-emerald-800/70 hover:text-emerald-600" : "text-emerald-100/70 hover:text-white",
            )}
          >
            使用流程
          </a>
          <Link
            to="/exercises"
            className={cn(
              "text-sm font-medium transition-colors",
              scrolled ? "text-emerald-800/70 hover:text-emerald-600" : "text-emerald-100/70 hover:text-white",
            )}
          >
            动作库
          </Link>
          <a
            href="https://github.com/fly-peach/fit-cream"
            target="_blank"
            rel="noopener noreferrer"
            aria-label="GitHub 仓库"
            className={cn(
              "inline-flex items-center gap-1.5 text-sm font-medium transition-colors",
              scrolled
                ? "text-emerald-800/70 hover:text-emerald-600"
                : "text-emerald-100/70 hover:text-white",
            )}
          >
            <GithubIcon className="size-4" />
            <span className="hidden lg:inline">GitHub</span>
          </a>
          {!isAuthenticated && (
            <Link
              to="/login"
              className={cn(
                "text-sm font-semibold transition-colors",
                scrolled ? "text-emerald-700 hover:text-emerald-500" : "text-emerald-100 hover:text-white",
              )}
            >
              登录
            </Link>
          )}
          <Link
            to={isAuthenticated ? "/dashboard" : "/login"}
            className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-emerald-600 to-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-emerald-600/25 transition-all hover:shadow-emerald-500/35 hover:brightness-105 active:scale-[0.98]"
          >
            {isAuthenticated ? "进入工作台" : "开始使用"}
            <ArrowRightIcon className="size-3.5" />
          </Link>
        </div>

        {/* 移动端菜单按钮 */}
        <button
          type="button"
          onClick={onToggle}
          aria-label="切换菜单"
          className={cn(
            "rounded-lg p-2 transition-colors md:hidden",
            scrolled ? "text-emerald-900 hover:bg-emerald-100" : "text-white hover:bg-white/10",
          )}
        >
          {open ? <XIcon className="size-5" /> : <MenuIcon className="size-5" />}
        </button>
      </nav>

      {/* 移动端下拉菜单 */}
      {open && (
        <motion.div
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          className="border-t border-emerald-100/60 bg-white/95 backdrop-blur-xl md:hidden"
        >
          <div className="mx-auto flex max-w-6xl flex-col gap-1 px-4 py-3">
            {[
              { label: "功能特性", href: "#features" },
              { label: "使用流程", href: "#how" },
              { label: "动作库", href: "/exercises" },
              { label: "GitHub", href: "https://github.com/fly-peach/fit-cream" },
              ...(isAuthenticated ? [] : [{ label: "登录", href: "/login" }]),
            ].map((item) => (
              <a
                key={item.label}
                href={item.href}
                target={item.href.startsWith("http") ? "_blank" : undefined}
                rel={item.href.startsWith("http") ? "noopener noreferrer" : undefined}
                className="rounded-lg px-3 py-2.5 text-sm font-medium text-emerald-900 transition-colors hover:bg-emerald-50"
              >
                {item.label}
              </a>
            ))}
            <Link
              to={isAuthenticated ? "/dashboard" : "/login"}
              className="mt-1 inline-flex items-center justify-center gap-1.5 rounded-full bg-gradient-to-r from-emerald-600 to-teal-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-600/25"
            >
              {isAuthenticated ? "进入工作台" : "开始使用"}
              <ArrowRightIcon className="size-3.5" />
            </Link>
          </div>
        </motion.div>
      )}
    </motion.header>
  );
}

/* ------------------------------ 模拟应用窗口 ------------------------------ */

function ChatMock() {
  return (
    <div className="relative">
      {/* 浮动统计标签 */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.7, duration: 0.6 }}
        className="home-float absolute -top-6 -left-4 z-20 flex items-center gap-2 rounded-2xl border border-emerald-400/25 bg-emerald-950/80 px-3.5 py-2.5 shadow-xl shadow-emerald-950/40 backdrop-blur-md sm:-left-10"
      >
        <FlameIcon className="size-4 text-orange-400" />
        <div>
          <p className="text-[10px] text-emerald-300/70">连续打卡</p>
          <p className="text-sm font-bold text-white">12 天</p>
        </div>
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.85, duration: 0.6 }}
        className="home-float absolute -right-4 top-1/3 z-20 flex items-center gap-2 rounded-2xl border border-emerald-400/25 bg-emerald-950/80 px-3.5 py-2.5 shadow-xl shadow-emerald-950/40 backdrop-blur-md [animation-delay:1.4s] sm:-right-8"
      >
        <CalendarDaysIcon className="size-4 text-emerald-400" />
        <div>
          <p className="text-[10px] text-emerald-300/70">本周完成</p>
          <p className="text-sm font-bold text-white">3 / 5 训练日</p>
        </div>
      </motion.div>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 1, duration: 0.6 }}
        className="home-float absolute -bottom-6 left-10 z-20 flex items-center gap-2 rounded-2xl border border-emerald-400/25 bg-emerald-950/80 px-3.5 py-2.5 shadow-xl shadow-emerald-950/40 backdrop-blur-md sm:left-16"
      >
        <ClipboardListIcon className="size-4 text-amber-400" />
        <div>
          <p className="text-[10px] text-emerald-300/70">计划本周</p>
          <p className="text-sm font-bold text-white">增肌 · 五分化</p>
        </div>
      </motion.div>

      {/* 窗口主体 */}
      <motion.div
        initial={{ opacity: 0, y: 32, rotateX: 8 }}
        animate={{ opacity: 1, y: 0, rotateX: 0 }}
        transition={{ delay: 0.35, duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 overflow-hidden rounded-3xl border border-white/10 bg-emerald-950/60 shadow-2xl shadow-emerald-950/50 backdrop-blur-xl"
        style={{ perspective: 1000 }}
      >
        {/* 标题栏 */}
        <div className="flex items-center gap-2 border-b border-white/5 px-4 py-3">
          <span className="size-2.5 rounded-full bg-red-400/80" />
          <span className="size-2.5 rounded-full bg-amber-400/80" />
          <span className="size-2.5 rounded-full bg-emerald-400/80" />
          <div className="ml-3 flex items-center gap-1.5 text-xs font-medium text-emerald-200/80">
            <BotIcon className="size-3.5 text-emerald-400" />
            FitCream · 计划助手
          </div>
          <span className="ml-auto flex items-center gap-1 rounded-full bg-emerald-400/10 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
            <span className="size-1.5 rounded-full bg-emerald-400" />
            在线
          </span>
        </div>

        {/* 对话区 */}
        <div className="space-y-3 px-4 py-4">
          {/* AI 思考过程 */}
          <div className="flex items-center gap-2 rounded-xl border border-emerald-400/10 bg-emerald-400/5 px-3 py-2">
            <SparklesIcon className="size-3.5 shrink-0 text-emerald-400" />
            <div className="home-shimmer h-2 flex-1 rounded-full" />
          </div>
          {/* AI 消息 */}
          <div className="flex items-start gap-2.5">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600">
              <BotIcon className="size-4 text-white" />
            </div>
            <div className="max-w-[85%] rounded-2xl rounded-tl-sm border border-white/10 bg-white/5 px-3.5 py-2.5 text-xs leading-relaxed text-emerald-50">
              <p>本周训练计划已生成 📋 周一胸 / 周三背 / 周五腿，详细动作、组数与重量都已写入你的计划页，按身体状态随时可调整。</p>
              <p className="mt-1.5 flex items-center gap-1 text-emerald-300/80">
                5 个训练日 · 18 个动作
                <ChevronRightIcon className="size-3" />
              </p>
            </div>
          </div>
          {/* 用户消息 */}
          <div className="flex items-start justify-end gap-2.5">
            <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-gradient-to-r from-emerald-500/90 to-teal-500/90 px-3.5 py-2.5 text-xs leading-relaxed text-white">
              这两周膝盖不太舒服，帮我把周五的腿日调整成低冲击版本。
            </div>
          </div>
          {/* 流式回复 */}
          <div className="flex items-start gap-2.5">
            <div className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600">
              <BotIcon className="size-4 text-white" />
            </div>
            <div className="rounded-2xl rounded-tl-sm border border-white/10 bg-white/5 px-3.5 py-3">
              <span className="flex gap-1">
                <span className="home-dot size-1.5 rounded-full bg-emerald-300" />
                <span className="home-dot size-1.5 rounded-full bg-emerald-300 [animation-delay:0.15s]" />
                <span className="home-dot size-1.5 rounded-full bg-emerald-300 [animation-delay:0.3s]" />
              </span>
            </div>
          </div>
        </div>

        {/* 输入条 */}
        <div className="border-t border-white/5 px-4 py-3">
          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/5 px-3 py-2.5">
            <PaperclipIcon className="size-4 shrink-0 text-emerald-300/60" />
            <span className="flex-1 text-xs text-emerald-200/40">帮我排一份减脂期的一周训练+饮食计划？</span>
            <span className="flex size-6 shrink-0 items-center justify-center rounded-lg bg-emerald-400 text-emerald-950">
              <ArrowRightIcon className="size-3.5" />
            </span>
          </div>
        </div>
      </motion.div>
    </div>
  );
}

/* ------------------------------ Hero ------------------------------ */

function Hero() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return (
    <section id="top" className="relative overflow-hidden bg-emerald-950">
      {/* 分层背景：光晕 + 网格 + 心电图 */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute -top-32 -left-32 size-[30rem] rounded-full bg-emerald-500/25 blur-3xl" />
        <div className="absolute right-0 bottom-0 size-[26rem] translate-x-1/3 translate-y-1/3 rounded-full bg-teal-400/20 blur-3xl" />
        <div className="absolute top-1/3 left-1/2 size-80 -translate-x-1/2 rounded-full bg-green-400/10 blur-3xl" />
        <div
          className="absolute inset-0 opacity-[0.06]"
          style={{
            backgroundImage:
              "linear-gradient(to right, #34d399 1px, transparent 1px), linear-gradient(to bottom, #34d399 1px, transparent 1px)",
            backgroundSize: "56px 56px",
          }}
        />
        {/* 底部心电图 */}
        <svg
          viewBox="0 0 640 80"
          className="absolute bottom-8 left-1/2 w-[120%] max-w-4xl -translate-x-1/2 text-emerald-400/25"
          fill="none"
          aria-hidden
        >
          <path
            d="M0 40 H180 L200 40 L212 12 L226 66 L240 30 L252 40 H320 L338 40 L350 8 L366 72 L382 26 L394 40 H640"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="ecg-line"
          />
        </svg>
      </div>

      {/* 浮动图标 */}
      <div className="pointer-events-none absolute top-[16%] right-[6%] float-slow hidden lg:block">
        <DumbbellIcon className="size-8 text-emerald-400/35" />
      </div>
      <div className="pointer-events-none absolute top-[44%] right-[12%] float-slow hidden lg:block [animation-delay:1.2s]">
        <HeartPulseIcon className="size-6 text-emerald-400/30" />
      </div>
      <div className="pointer-events-none absolute bottom-[18%] left-[4%] float-slow hidden lg:block [animation-delay:2s]">
        <TrophyIcon className="size-7 text-amber-400/30" />
      </div>

      <div className="relative mx-auto grid max-w-6xl gap-14 px-4 pt-32 pb-28 sm:px-6 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:gap-10 lg:pt-40 lg:pb-36">
        {/* 左侧文案 */}
        <motion.div variants={stagger} initial="hidden" animate="show">
          <motion.div
            variants={fadeUp}
            className="inline-flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-1.5 text-xs font-semibold text-emerald-200 backdrop-blur-sm"
          >
            <SparkleIcon className="size-3.5 text-emerald-400" />
            训练与饮食计划助手 · 科学健身的陪伴者
          </motion.div>

          <motion.h1
            variants={fadeUp}
            className="mt-6 font-display text-5xl leading-[1.08] font-bold tracking-tight text-white sm:text-6xl lg:text-7xl"
          >
            把汗水，
            <br />
            变成<span className="text-emerald-400">答案</span>。
          </motion.h1>

          <motion.p
            variants={fadeUp}
            className="mt-6 max-w-lg text-base leading-relaxed text-emerald-200/80 sm:text-lg"
          >
            按你的目标与身体数据定制训练与饮食计划，
            打卡记录、复盘数据、管理动作与知识库，一路陪你坚持下去。
          </motion.p>

          <motion.div variants={fadeUp} className="mt-9 flex flex-wrap items-center gap-4">
            <Link
              to={isAuthenticated ? "/dashboard" : "/login"}
              className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 px-7 py-3.5 text-base font-semibold text-white shadow-xl shadow-emerald-500/30 transition-all hover:shadow-emerald-400/40 hover:brightness-110 active:scale-[0.98]"
            >
              {isAuthenticated ? "进入工作台" : "免费开始使用"}
              <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="#features"
              className="inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-400/10 px-7 py-3.5 text-base font-semibold text-emerald-100 backdrop-blur-sm transition-all hover:border-emerald-400/60 hover:bg-emerald-400/20"
            >
              了解功能
            </a>
          </motion.div>

          {/* 特性标签 */}
          <motion.div variants={fadeUp} className="mt-10 flex flex-wrap gap-3">
            {[
              { icon: ClipboardListIcon, label: "训练与饮食计划" },
              { icon: CalendarCheckIcon, label: "打卡与数据复盘" },
              { icon: ShieldCheckIcon, label: "服务端会话 · 数据安全" },
            ].map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="flex items-center gap-2 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-4 py-2 text-sm font-medium text-emerald-200 backdrop-blur-sm"
              >
                <Icon className="size-4 text-emerald-400" />
                {label}
              </span>
            ))}
          </motion.div>
        </motion.div>

        {/* 右侧模拟窗口 */}
        <motion.div variants={stagger} initial="hidden" animate="show" className="relative">
          <motion.div variants={fadeUp}>
            <ChatMock />
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}

/* ------------------------------ 功能特性 ------------------------------ */

const FEATURES = [
  {
    icon: MessageSquareIcon,
    title: "AI 对话管理计划",
    desc: "用自然语言生成、调整训练与饮食计划，思考过程清晰可见，支持图片附件。",
    to: "/chat",
    tint: "bg-emerald-100 text-emerald-600",
  },
  {
    icon: CalendarCheckIcon,
    title: "周计划安排",
    desc: "按周组织训练日，动作、组数、重量与饮食方案集中管理，随时按状态调整。",
    to: "/plans",
    tint: "bg-teal-100 text-teal-600",
  },
  {
    icon: AppleIcon,
    title: "饮食营养记录",
    desc: "每餐热量与蛋白质 / 碳水 / 脂肪一目了然，对照目标追踪宏量营养素。",
    to: "/plans",
    tint: "bg-amber-100 text-amber-600",
  },
  {
    icon: BarChart3Icon,
    title: "打卡与数据看板",
    desc: "训练打卡、连续纪录、训练量与心情趋势一屏掌握，用数据见证进步。",
    to: "/dashboard",
    tint: "bg-sky-100 text-sky-600",
  },
  {
    icon: DumbbellIcon,
    title: "动作库与收藏",
    desc: "动作搜索、标准做法随时查阅，支持收藏与详情页查看，练得规范更安全。",
    to: "/exercises",
    tint: "bg-emerald-100 text-emerald-600",
  },
  {
    icon: BookOpenIcon,
    title: "专属知识库",
    desc: "沉淀健身知识、笔记与参考资料，对话中可直接调用，越用越贴个人需求。",
    to: "/knowledge-bases",
    tint: "bg-violet-100 text-violet-600",
  },
];

function Features() {
  return (
    <section id="features" className="relative overflow-hidden bg-gradient-to-b from-emerald-50 via-white to-teal-50">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-0 left-1/2 size-[24rem] -translate-x-1/2 rounded-full bg-emerald-200/40 blur-3xl" />
        <div className="absolute bottom-0 -left-24 size-72 rounded-full bg-teal-200/30 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:py-28">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-2xl text-center"
        >
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-white/80 px-3.5 py-1 text-xs font-semibold text-emerald-600 backdrop-blur-sm">
            <SparkleIcon className="size-3.5" />
            一站式科学健身管理
          </span>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-emerald-950 sm:text-4xl">
            计划 · 打卡 · 复盘
            <br className="sm:hidden" /> 让坚持有据可循
          </h2>
          <p className="mt-4 text-base leading-relaxed text-emerald-700/60">
            从训练与饮食计划生成，到每日执行、打卡记录、数据复盘，
            FitCream 帮你把每一次训练与饮食管理起来。
          </p>
        </motion.div>

        <motion.div
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-60px" }}
          className="mt-14 grid gap-4 sm:grid-cols-2 sm:gap-5 lg:grid-cols-3"
        >
          {FEATURES.map(({ icon: Icon, title, desc, to, tint }) => (
            <motion.div key={title} variants={fadeUp}>
              <Link
                to={to}
                className="group flex h-full flex-col rounded-3xl border border-emerald-100/80 bg-white/80 p-6 shadow-sm backdrop-blur transition-all duration-300 hover:-translate-y-1 hover:border-emerald-200 hover:shadow-xl hover:shadow-emerald-500/10"
              >
                <div
                  className={cn(
                    "flex size-11 items-center justify-center rounded-2xl transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-3",
                    tint,
                  )}
                >
                  <Icon className="size-5" />
                </div>
                <h3 className="mt-4 font-display text-lg font-bold tracking-tight text-emerald-950">
                  {title}
                </h3>
                <p className="mt-2 flex-1 text-sm leading-relaxed text-emerald-700/60">{desc}</p>
                <span className="mt-4 inline-flex items-center gap-1 text-sm font-semibold text-emerald-600 transition-colors group-hover:text-emerald-500">
                  立即体验
                  <ArrowRightIcon className="size-3.5 transition-transform group-hover:translate-x-1" />
                </span>
              </Link>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ------------------------------ 使用流程 ------------------------------ */

const STEPS = [
  {
    icon: TargetIcon,
    step: "01",
    title: "定计划",
    desc: "告诉 AI 你的目标与身体数据，一周训练 + 饮食计划自动生成。",
  },
  {
    icon: CalendarCheckIcon,
    step: "02",
    title: "坚持做",
    desc: "按计划训练、记录饮食、每日打卡，计划可随时对话调整。",
  },
  {
    icon: BarChart3Icon,
    step: "03",
    title: "看变化",
    desc: "数据看板沉淀连续纪录、训练量与心情趋势，用数据看见进步。",
  },
];

function HowItWorks() {
  return (
    <section id="how" className="relative overflow-hidden bg-emerald-950">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute top-0 right-0 size-80 translate-x-1/4 -translate-y-1/4 rounded-full bg-emerald-500/15 blur-3xl" />
        <div className="absolute bottom-0 left-0 size-72 -translate-x-1/4 translate-y-1/4 rounded-full bg-teal-400/10 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 py-20 sm:px-6 lg:py-28">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-80px" }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="mx-auto max-w-2xl text-center"
        >
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-400/25 bg-emerald-400/10 px-3.5 py-1 text-xs font-semibold text-emerald-300 backdrop-blur-sm">
            <SparkleIcon className="size-3.5" />
            三步科学健身
          </span>
          <h2 className="mt-4 font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
            科学健身，<span className="text-emerald-400">循序渐进</span>
          </h2>
        </motion.div>

        <motion.div
          variants={stagger}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, margin: "-60px" }}
          className="relative mt-14 grid gap-6 sm:grid-cols-3"
        >
          {/* 连接线（桌面） */}
          <div className="pointer-events-none absolute top-12 right-[16%] left-[16%] hidden h-px bg-gradient-to-r from-transparent via-emerald-400/30 to-transparent sm:block" />
          {STEPS.map(({ icon: Icon, step, title, desc }) => (
            <motion.div
              key={step}
              variants={fadeUp}
              className="relative rounded-3xl border border-white/10 bg-white/5 p-7 text-center backdrop-blur-sm transition-colors duration-300 hover:border-emerald-400/30 hover:bg-white/10"
            >
              <span className="absolute top-4 right-5 font-display text-sm font-bold text-emerald-400/40">
                {step}
              </span>
              <div className="relative mx-auto flex size-14 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 shadow-lg shadow-emerald-500/30">
                <Icon className="size-6 text-white" />
              </div>
              <h3 className="mt-5 font-display text-xl font-bold tracking-tight text-white">{title}</h3>
              <p className="mt-2.5 text-sm leading-relaxed text-emerald-200/70">{desc}</p>
            </motion.div>
          ))}
        </motion.div>
      </div>
    </section>
  );
}

/* ------------------------------ CTA ------------------------------ */

function CtaBanner() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-white to-emerald-50">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6 lg:py-20">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-60px" }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="relative overflow-hidden rounded-[2rem] bg-gradient-to-br from-emerald-600 via-emerald-600 to-teal-700 px-6 py-14 text-center shadow-2xl shadow-emerald-600/25 sm:px-12 lg:py-16"
        >
          <div className="pointer-events-none absolute inset-0">
            <div className="absolute -top-20 -left-20 size-64 rounded-full bg-emerald-400/25 blur-3xl" />
            <div className="absolute -right-16 -bottom-24 size-72 rounded-full bg-teal-300/25 blur-3xl" />
            <div
              className="absolute inset-0 opacity-[0.07]"
              style={{
                backgroundImage:
                  "linear-gradient(to right, #ffffff 1px, transparent 1px), linear-gradient(to bottom, #ffffff 1px, transparent 1px)",
                backgroundSize: "40px 40px",
              }}
            />
          </div>
          <div className="relative">
            <h2 className="mx-auto max-w-2xl font-display text-3xl font-bold tracking-tight text-white sm:text-4xl">
              现在就开启你的科学健身之旅
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-base leading-relaxed text-emerald-100/85">
              无需复杂配置，注册即用。定计划、记饮食、打卡复盘，一路相伴坚持到底。
            </p>
            <Link
              to={isAuthenticated ? "/dashboard" : "/login"}
              className="group mt-8 inline-flex items-center gap-2 rounded-full bg-white px-8 py-3.5 text-base font-bold text-emerald-700 shadow-lg transition-all hover:shadow-xl hover:brightness-95 active:scale-[0.98]"
            >
              {isAuthenticated ? "进入工作台" : "免费开始使用"}
              <ArrowRightIcon className="size-4 transition-transform group-hover:translate-x-1" />
            </Link>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

/* ------------------------------ 页脚 ------------------------------ */

function Footer() {
  const links = [
    { label: "AI 计划助手", to: "/chat" },
    { label: "训练计划", to: "/plans" },
    { label: "动作库", to: "/exercises" },
    { label: "数据看板", to: "/dashboard" },
    { label: "知识库", to: "/knowledge-bases" },
  ];
  return (
    <footer className="border-t border-white/10 bg-emerald-950">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="flex flex-col gap-10 md:flex-row md:items-start md:justify-between">
          <div className="max-w-sm">
            <div className="flex items-center gap-2.5">
              <Logo className="size-9 rounded-xl shadow-md shadow-emerald-500/25" />
              <span className="font-display text-xl font-bold tracking-tight text-white">
                Fit<span className="text-emerald-400">Cream</span>
              </span>
            </div>
            <p className="mt-4 text-sm leading-relaxed text-emerald-200/60">
              训练与饮食计划助手 —— 把汗水，变成答案。
              计划 · 打卡 · 复盘 · 持之以恒。
            </p>
          </div>
          <div>
            <p className="text-sm font-semibold text-emerald-100">快速导航</p>
            <ul className="mt-4 grid grid-cols-2 gap-x-8 gap-y-2.5 sm:grid-cols-1">
              {links.map((item) => (
                <li key={item.label}>
                  <Link
                    to={item.to}
                    className="text-sm text-emerald-200/60 transition-colors hover:text-emerald-300"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
          <div>
            <p className="text-sm font-semibold text-emerald-100">账户</p>
            <ul className="mt-4 space-y-2.5">
              <li>
                <Link to="/login" className="text-sm text-emerald-200/60 transition-colors hover:text-emerald-300">
                  登录 / 注册
                </Link>
              </li>
              <li>
                <Link to="/profile" className="text-sm text-emerald-200/60 transition-colors hover:text-emerald-300">
                  个人中心
                </Link>
              </li>
            </ul>
          </div>
        </div>
        <div className="mt-10 flex flex-col items-center justify-between gap-3 border-t border-white/10 pt-6 sm:flex-row">
          <p className="text-xs text-emerald-200/40">
            © {new Date().getFullYear()} FitCream · AI 智能健身教练
          </p>
          <p className="flex items-center gap-1.5 text-xs text-emerald-200/40">
            <ShieldCheckIcon className="size-3.5 text-emerald-400/60" />
            数据加密存储 · 服务端会话守护
          </p>
        </div>
      </div>
    </footer>
  );
}

/* ------------------------------ 首页 ------------------------------ */

export default function HomePage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="scroll-smooth bg-emerald-50 font-sans antialiased">
      <style>{HOME_STYLE}</style>
      <HomeNav
        scrolled={scrolled}
        open={menuOpen}
        onToggle={() => setMenuOpen((v) => !v)}
        isAuthenticated={isAuthenticated}
      />
      <main>
        <Hero />
        <Features />
        <HowItWorks />
        <CtaBanner />
      </main>
      <Footer />
    </div>
  );
}
