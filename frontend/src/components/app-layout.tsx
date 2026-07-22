import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DumbbellIcon,
  LayoutDashboardIcon,
  MessageSquareIcon,
  ClipboardListIcon,
  CalendarCheckIcon,
  UserIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  LogOutIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

const navItems = [
  { to: "/dashboard", label: "工作台", icon: LayoutDashboardIcon },
  { to: "/chat", label: "AI 教练", icon: MessageSquareIcon },
  { to: "/plans", label: "训练计划", icon: ClipboardListIcon },
  { to: "/checkins", label: "打卡记录", icon: CalendarCheckIcon },
  { to: "/profile", label: "个人中心", icon: UserIcon },
];

interface AppLayoutProps {
  children: React.ReactNode;
  /** 侧边栏底部插槽（如对话历史列表） */
  sidebarExtra?: React.ReactNode;
}

export function AppLayout({ children, sidebarExtra }: AppLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const { logout } = useAuthStore();

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-emerald-50/80 via-white to-teal-50/60">
      {/* 侧边栏 */}
      <aside
        className={cn(
          "flex flex-col border-r border-emerald-100 bg-gradient-to-b from-emerald-50/80 to-white/90 backdrop-blur transition-all duration-200",
          collapsed ? "w-16" : "w-60"
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 border-b border-emerald-100 px-4 py-4">
          <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-600 shadow-sm shadow-emerald-500/20">
            <DumbbellIcon className="size-4 text-white" />
          </div>
          {!collapsed && (
            <span className="text-base font-bold tracking-tight text-emerald-950">
              Fit<span className="text-emerald-600">Cream</span>
            </span>
          )}
        </div>

        {/* 导航菜单 */}
        <nav className="space-y-1 px-2 pt-3">
          {navItems.map((item) => {
            const isActive = location.pathname.startsWith(item.to);
            return (
              <Link
                key={item.to}
                to={item.to}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-emerald-100/80 text-emerald-800"
                    : "text-emerald-700/70 hover:bg-emerald-100/60 hover:text-emerald-800"
                )}
                title={collapsed ? item.label : undefined}
              >
                <item.icon
                  className={cn("size-4 shrink-0", isActive && "text-emerald-500")}
                />
                {!collapsed && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* 侧边栏额外内容（如对话历史） */}
        {sidebarExtra && !collapsed && (
          <div className="flex-1 overflow-hidden">{sidebarExtra}</div>
        )}
        {sidebarExtra && collapsed && <div className="flex-1" />}
        {!sidebarExtra && <div className="flex-1" />}

        {/* 底部操作 */}
        <div className="border-t border-emerald-100 p-2 space-y-1">
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "w-full text-emerald-700/70 hover:bg-emerald-100/60 hover:text-emerald-800",
              collapsed ? "justify-center px-2" : "justify-start"
            )}
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? (
              <PanelLeftOpenIcon className="size-4" />
            ) : (
              <>
                <PanelLeftCloseIcon className="size-4" />
                <span className="ml-2 text-xs">收起</span>
              </>
            )}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className={cn(
              "w-full text-emerald-700/70 hover:bg-red-50 hover:text-red-600",
              collapsed ? "justify-center px-2" : "justify-start"
            )}
            onClick={logout}
          >
            <LogOutIcon className="size-4" />
            {!collapsed && <span className="ml-2 text-xs">退出登录</span>}
          </Button>
        </div>
      </aside>

      {/* 主内容区 */}
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}