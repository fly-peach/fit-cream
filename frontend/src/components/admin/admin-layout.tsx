import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboardIcon,
  UsersIcon,
  BookOpenIcon,
  ShieldIcon,
  ArrowLeftIcon,
  LogOutIcon,
  MenuIcon,
  XIcon,
  PanelLeftCloseIcon,
  PanelLeftOpenIcon,
} from "lucide-react";
import { Button, buttonVariants } from "@/components/ui/button";
import { Logo } from "@/components/logo";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/auth-store";

/** 管理端导航项（分组导航，按顺序渲染） */
const adminNavItems = [
  { to: "/admin/overview", label: "总览", icon: LayoutDashboardIcon },
  { to: "/admin/users", label: "用户管理", icon: UsersIcon },
  { to: "/admin/knowledge-bases", label: "知识库管理", icon: BookOpenIcon },
];

function findNavItem(pathname: string) {
  return adminNavItems.find((item) => pathname.startsWith(item.to));
}

/** 计算面包屑：[管理后台, 分组, 详情页名?] */
function useBreadcrumbs() {
  const location = useLocation();
  const item = findNavItem(location.pathname);
  const crumbs = [{ label: "管理后台" }];
  if (item) crumbs.push({ label: item.label });
  const rest = location.pathname
    .replace(item?.to ?? "", "")
    .split("/")
    .filter(Boolean);
  if (rest.length > 0) crumbs.push({ label: "详情" });
  return crumbs;
}

interface AdminLayoutProps {
  children: React.ReactNode;
}

export function AdminLayout({ children }: AdminLayoutProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { logout } = useAuthStore();
  const breadcrumbs = useBreadcrumbs();

  const renderNav = (closeOnClick: boolean) =>
    adminNavItems.map((item) => {
      const isActive = location.pathname.startsWith(item.to);
      return (
        <Link
          key={item.to}
          to={item.to}
          onClick={closeOnClick ? () => setMobileOpen(false) : undefined}
          className={cn(
            "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive
              ? "bg-emerald-100/80 text-emerald-800"
              : "text-emerald-700/70 hover:bg-emerald-100/60 hover:text-emerald-800"
          )}
          title={collapsed ? item.label : undefined}
        >
          <item.icon className={cn("size-4 shrink-0", isActive && "text-emerald-500")} />
          {!collapsed && <span>{item.label}</span>}
        </Link>
      );
    });

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-emerald-50/80 via-white to-teal-50/60">
      {/* ============ 桌面端侧边栏 ============ */}
      <aside
        className={cn(
          "hidden flex-col border-r border-emerald-100 bg-gradient-to-b from-emerald-50/80 to-white/90 backdrop-blur transition-all duration-200 md:flex",
          collapsed ? "w-16" : "w-60"
        )}
      >
        <div className="flex items-center gap-2.5 border-b border-emerald-100 px-4 py-4">
          <Logo className="size-8 shrink-0 rounded-lg shadow-sm shadow-emerald-500/20" />
          {!collapsed && (
            <span className="text-base font-bold tracking-tight text-emerald-950">
              Fit<span className="text-emerald-600">Cream</span>
              <span className="ml-1.5 rounded-md bg-emerald-600/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-600">
                管理
              </span>
            </span>
          )}
        </div>

        <nav className="space-y-1 px-2 pt-3">
          <p
            className={cn(
              "px-3 pb-1 text-[10px] font-semibold uppercase tracking-widest text-emerald-600/50",
              collapsed && "px-0 text-center"
            )}
          >
            {collapsed ? "·" : "管理"}
          </p>
          {renderNav(false)}
        </nav>

        <div className="flex-1" />

        <div className="space-y-1 border-t border-emerald-100 p-2">
          <Link
            to="/dashboard"
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
              "w-full text-emerald-700/70 hover:bg-emerald-100/60 hover:text-emerald-800",
              collapsed ? "justify-center px-2" : "justify-start"
            )}
          >
            <ArrowLeftIcon className="size-4" />
            {!collapsed && <span className="ml-1.5 text-xs">返回用户端</span>}
          </Link>
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

      {/* ============ 移动端抽屉 ============ */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-emerald-100 bg-white shadow-2xl transition-transform duration-200 md:hidden",
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex items-center justify-between border-b border-emerald-100 px-4 py-4">
          <div className="flex items-center gap-2.5">
            <Logo className="size-8 shrink-0 rounded-lg shadow-sm shadow-emerald-500/20" />
            <span className="text-base font-bold tracking-tight text-emerald-950">
              Fit<span className="text-emerald-600">Cream</span>
              <span className="ml-1.5 rounded-md bg-emerald-600/10 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-600">
                管理
              </span>
            </span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="size-8 text-emerald-700"
            onClick={() => setMobileOpen(false)}
          >
            <XIcon className="size-4" />
          </Button>
        </div>
        <nav className="space-y-1 px-2 pt-3">{renderNav(true)}</nav>
        <div className="flex-1" />
        <div className="space-y-1 border-t border-emerald-100 p-2">
          <Link
            to="/dashboard"
            onClick={() => setMobileOpen(false)}
            className="flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium text-emerald-700/70 hover:bg-emerald-100/60 hover:text-emerald-800"
          >
            <ArrowLeftIcon className="size-4" />
            <span className="text-xs">返回用户端</span>
          </Link>
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start text-emerald-700/70 hover:bg-red-50 hover:text-red-600"
            onClick={() => logout()}
          >
            <LogOutIcon className="size-4" />
            <span className="ml-2 text-xs">退出登录</span>
          </Button>
        </div>
      </aside>

      {/* ============ 主内容区 ============ */}
      <main className="flex flex-1 flex-col overflow-hidden pb-16 md:pb-0">
        <header className="flex items-center gap-2 border-b border-emerald-100 bg-white/70 px-4 py-2.5 backdrop-blur">
          <Button
            variant="ghost"
            size="icon"
            className="size-9 text-emerald-700 md:hidden"
            onClick={() => setMobileOpen(true)}
          >
            <MenuIcon className="size-5" />
          </Button>
          <nav className="flex min-w-0 items-center gap-1.5 text-sm">
            <ShieldIcon className="size-4 shrink-0 text-emerald-500" />
            {breadcrumbs.map((crumb, i) => (
              <span key={i} className="flex items-center gap-1.5">
                {i > 0 && <span className="text-emerald-300">/</span>}
                <span
                  className={cn(
                    "truncate",
                    i === breadcrumbs.length - 1
                      ? "font-semibold text-emerald-900"
                      : "text-emerald-600/60"
                  )}
                >
                  {crumb.label}
                </span>
              </span>
            ))}
          </nav>
        </header>
        <div className="flex-1 overflow-hidden">{children}</div>
      </main>
    </div>
  );
}
