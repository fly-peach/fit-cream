import { useId } from "react";
import { cn } from "@/lib/utils";

/**
 * FitCream 品牌 Logo：翡翠渐变圆角底 + 知识哑铃（打开的书作手柄，两侧杠铃片）+ AI Spark。
 * 与 public/favicon.svg 同源设计，保证浏览器标签与站内品牌一致。
 */
export function Logo({ className }: { className?: string }) {
  const gid = useId();
  return (
    <svg
      viewBox="0 0 64 64"
      className={cn("size-8", className)}
      role="img"
      aria-label="FitCream"
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#10b981" />
          <stop offset="1" stopColor="#0d9488" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="18" fill={`url(#${gid})`} />
      <g fill="#ffffff">
        {/* 杠铃片 */}
        <rect x="7" y="20" width="11" height="24" rx="4" />
        <rect x="46" y="20" width="11" height="24" rx="4" />
        {/* 打开的书（中央手柄，象征知识库） */}
        <path d="M32 24 L17 29 L17 47 L32 42 Z" />
        <path d="M32 24 L47 29 L47 47 L32 42 Z" />
      </g>
      {/* 书脊中缝 */}
      <path d="M32 24 L32 42" stroke="#6ee7b7" strokeWidth="1.5" strokeLinecap="round" />
      {/* AI Spark（右上角） */}
      <path
        d="M54 9 L55.4 13.6 L60 15 L55.4 16.4 L54 21 L52.6 16.4 L48 15 L52.6 13.6 Z"
        fill="#d1fae5"
      />
    </svg>
  );
}
