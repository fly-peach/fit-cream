import { Navigate } from "react-router-dom";
import { useAuthStore } from "@/stores/auth-store";

/**
 * 仅管理员可访问的路由守卫。
 *
 * - 未登录 -> /login
 * - 已登录但非 admin -> /knowledge-bases（用户端落地页）
 */
export function AdminRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const role = useAuthStore((s) => s.user?.role);

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  if (role !== "admin") {
    return <Navigate to="/knowledge-bases" replace />;
  }
  return <>{children}</>;
}
