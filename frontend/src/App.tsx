import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { Capacitor } from "@capacitor/core";
import { useAuthStore } from "@/stores/auth-store";
import { AdminRoute } from "@/components/admin-route";
import { AdminLayout } from "@/components/admin/admin-layout";
import { LanguageProvider } from "@/lib/language-context";
import ChatPage from "@/pages/chat";
import DashboardPage from "@/pages/dashboard";
import DocumentViewerPage from "@/pages/document-viewer";
import ExercisesPage from "@/pages/exercises";
import ExerciseGroupPage from "@/pages/exercise-group";
import ExerciseGroupDetailPage from "@/pages/exercise-group-detail";
import ExerciseDetailPage from "@/pages/exercise-detail";
import KnowledgeBasesPage from "@/pages/knowledge-bases";
import KnowledgeBaseDetailPage from "@/pages/knowledge-base-detail";
import LoginPage from "@/pages/login";
import HomePage from "@/pages/home";
import PlansPage from "@/pages/plans";
import ProfilePage from "@/pages/profile";
import AdminOverviewPage from "@/pages/admin/overview";
import AdminUsersPage from "@/pages/admin/users";
import AdminUserDetailPage from "@/pages/admin/user-detail";
import KbManagementPage from "@/pages/admin/kb-management";
import KbDetailPage from "@/pages/admin/kb-detail";
import AdminSearchQualityPage from "@/pages/admin/search-quality";

/** 需要登录才能访问的路由守卫 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

/** 原生 App（Capacitor WebView）不展示首页：已登录直达工作台，未登录跳登录页；Web 端保留首页 */
const isNativeApp = Capacitor.isNativePlatform();

function EntryRoute() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (isNativeApp) {
    return isAuthenticated ? <Navigate to="/dashboard" replace /> : <Navigate to="/login" replace />;
  }
  return <HomePage />;
}

export function App() {
  const isInitialized = useAuthStore((s) => s.isInitialized);
  const fetchCurrentUser = useAuthStore((s) => s.fetchCurrentUser);

  // 启动时探测服务端会话（httpOnly Cookie 认证，无法从 localStorage 恢复）
  useEffect(() => {
    void fetchCurrentUser();
  }, [fetchCurrentUser]);

  // 会话探测完成前不渲染路由，避免受保护页面闪跳登录页
  if (!isInitialized) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-muted-foreground text-sm">
        加载中...
      </div>
    );
  }

  return (
    <LanguageProvider>
      <BrowserRouter>
        <Toaster position="top-center" richColors />
        <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<EntryRoute />} />

        {/* 用户端 */}
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <DashboardPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/chat/:sessionId"
          element={
            <ProtectedRoute>
              <ChatPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/plans"
          element={
            <ProtectedRoute>
              <PlansPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/plans/:exSegment/:dtSegment"
          element={
            <ProtectedRoute>
              <PlansPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/exercises"
          element={<Navigate to="/exercises/exercise-database" replace />}
        />
        <Route
          path="/exercises/exercise-database"
          element={
            <ProtectedRoute>
              <ExercisesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/exercises/exercise-group"
          element={
            <ProtectedRoute>
              <ExerciseGroupPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/exercises/exercise-group/:key"
          element={
            <ProtectedRoute>
              <ExerciseGroupDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/exercises/:id"
          element={
            <ProtectedRoute>
              <ExerciseDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge-bases"
          element={
            <ProtectedRoute>
              <KnowledgeBasesPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge-bases/:kbId"
          element={
            <ProtectedRoute>
              <KnowledgeBaseDetailPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/knowledge-bases/:kbId/documents/:docId"
          element={
            <ProtectedRoute>
              <DocumentViewerPage />
            </ProtectedRoute>
          }
        />
        <Route
          path="/profile"
          element={
            <ProtectedRoute>
              <ProfilePage />
            </ProtectedRoute>
          }
        />

        {/* 管理端 */}
        <Route
          path="/admin"
          element={
            <AdminRoute>
              <Navigate to="/admin/overview" replace />
            </AdminRoute>
          }
        />
        <Route
          path="/admin/overview"
          element={
            <AdminRoute>
              <AdminLayout>
                <AdminOverviewPage />
              </AdminLayout>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/users"
          element={
            <AdminRoute>
              <AdminLayout>
                <AdminUsersPage />
              </AdminLayout>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/users/:userId"
          element={
            <AdminRoute>
              <AdminLayout>
                <AdminUserDetailPage />
              </AdminLayout>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/knowledge-bases"
          element={
            <AdminRoute>
              <AdminLayout>
                <KbManagementPage />
              </AdminLayout>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/knowledge-bases/:kbId"
          element={
            <AdminRoute>
              <AdminLayout>
                <KbDetailPage />
              </AdminLayout>
            </AdminRoute>
          }
        />
        <Route
          path="/admin/search-quality"
          element={
            <AdminRoute>
              <AdminLayout>
                <AdminSearchQualityPage />
              </AdminLayout>
            </AdminRoute>
          }
        />
        </Routes>
      </BrowserRouter>
    </LanguageProvider>
  );
}

export default App;
