import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import { useAuthStore } from "@/stores/auth-store";
import { AdminRoute } from "@/components/admin-route";
import { LanguageProvider } from "@/lib/language-context";
import ChatPage from "@/pages/chat";
import DashboardPage from "@/pages/dashboard";
import DocumentViewerPage from "@/pages/document-viewer";
import ExercisesPage from "@/pages/exercises";
import ExerciseDetailPage from "@/pages/exercise-detail";
import KnowledgeBasesPage from "@/pages/knowledge-bases";
import KnowledgeBaseDetailPage from "@/pages/knowledge-base-detail";
import LoginPage from "@/pages/login";
import PlansPage from "@/pages/plans";
import ProfilePage from "@/pages/profile";
import KbManagementPage from "@/pages/admin/kb-management";
import KbDetailPage from "@/pages/admin/kb-detail";

/** 需要登录才能访问的路由守卫 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
}

export function App() {
  return (
    <LanguageProvider>
      <BrowserRouter>
        <Toaster position="top-center" richColors />
        <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/dashboard" replace />} />

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
          element={
            <ProtectedRoute>
              <ExercisesPage />
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
          path="/admin/knowledge-bases"
          element={
            <AdminRoute>
              <KbManagementPage />
            </AdminRoute>
          }
        />
        <Route
          path="/admin/knowledge-bases/:kbId"
          element={
            <AdminRoute>
              <KbDetailPage />
            </AdminRoute>
          }
        />
        </Routes>
      </BrowserRouter>
    </LanguageProvider>
  );
}

export default App;
