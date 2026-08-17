import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Button } from "@/components/ui/button";
import {
  DumbbellIcon,
  SunIcon,
  MessageSquareIcon,
  ClipboardListIcon,
  UserIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
  LogOutIcon,
  BookOpenIcon,
  ShieldIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";
import { Logo } from "@/components/logo";

/**
 * 全局导航项
 *
 * 桌面端：左侧侧边栏
 * 移动端：底部 Tab 栏（核心 5 项，不含管理后台）
 *
 * 所有登录用户可见：今日 / AI 教练 / 训练计划 / 知识库 / 我的
 * admin 额外可见：管理后台（仅侧边栏/抽屉，不在底部 Tab）
 */
function useNavItems() {
  const role = useAuthStore((s) => s.user?.role);
  const items = [
    { to: "/dashboard", label: "今日", icon: SunIcon },
    { to: "/chat", label: "AI 教练", icon: MessageSquareIcon },
    { to: "/plans", label: "训练计划", icon: ClipboardListIcon },
    { to: "/exercises", label: "动作库", icon: DumbbellIcon },
    { to: "/knowledge-bases", label: "知识库", icon: BookOpenIcon },
    { to: "/profile", label: "我的", icon: UserIcon },
  ];
  if (role === "admin") {
    items.push({ to: "/admin/overview", label: "管理后台", icon: ShieldIcon });
  }
  return items;
}

/** 底部 Tab 栏仅展示核心用户导航（不含管理后台，避免移动端拥挤） */
function useBottomNavItems() {
  return useNavItems().filter((i) => !i.to.startsWith("/admin"));
}

interface AppLayoutProps {
  children: React.ReactNode;
  /** 侧边栏底部插槽（如对话历史列表） */
  sidebarExtra?: React.ReactNode;
}

export function AppLayout({ children, sidebarExtra }: AppLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const location = useLocation();
  const { logout } = useAuthStore();
  const navItems = useNavItems();
  const bottomNavItems = useBottomNavItems();


  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-emerald-50/80 via-white to-teal-50/60">
      {/* ============ 桌面端侧边栏 ============ */}
      <aside
        className={cn(
          "hidden flex-col border-r border-emerald-100 bg-gradient-to-b from-emerald-50/80 to-white/90 backdrop-blur transition-all duration-200 md:flex",
          collapsed ? "w-16" : "w-60"
        )}
      >
        {/* Logo */}
        <div className="flex items-center gap-2.5 border-b border-emerald-100 px-4 py-4">
          <Logo className="size-8 shrink-0 rounded-lg shadow-sm shadow-emerald-500/20" />
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
        <div className="space-y-1 border-t border-emerald-100 p-2">
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
            onClick={() => logout()}
          >
            <LogOutIcon className="size-4" />
            {!collapsed && <span className="ml-2 text-xs">退出登录</span>}
          </Button>
        </div>
      </aside>


      {/* ============ 主内容区 ============ */}
      <main className="flex flex-1 flex-col overflow-hidden pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">

        <div className="flex-1 overflow-hidden">{children}</div>
      </main>

      {/* ============ 移动端底部 Tab 栏 ============ */}
      <nav className="fixed inset-x-0 bottom-0 z-30 flex items-stretch justify-around border-t border-emerald-100 bg-white/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden">
        {bottomNavItems.map((item) => {
          const isActive = location.pathname.startsWith(item.to);
          return (
            <Link
              key={item.to}
              to={item.to}
              className={cn(
                "flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-xs font-medium transition-colors",
                isActive
                  ? "text-emerald-600"
                  : "text-emerald-700/50 hover:text-emerald-700"
              )}
            >
              <item.icon
                className={cn(
                  "size-5 transition-transform",
                  isActive && "scale-110"
                )}
              />
              <span>{item.label}</span>
              {isActive && (
                <span className="absolute top-0 h-0.5 w-8 rounded-b-full bg-emerald-500" />
              )}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}