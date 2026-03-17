import { BrowserRouter, Routes, Route } from "react-router-dom";
import MainLayout from "@/layouts/MainLayout";
import MobileLayout from "@/layouts/MobileLayout";
import DashboardPage from "@/pages/DashboardPage";
import ProjectPage from "@/pages/ProjectPage";
import SessionPage from "@/pages/SessionPage";
import QuestionsPage from "@/pages/QuestionsPage";
import ReplayPage from "@/pages/ReplayPage";
import RolesPage from "@/pages/RolesPage";
import SearchPage from "@/pages/SearchPage";
import NewProjectPage from "@/pages/NewProjectPage";
import NotFoundPage from "@/pages/NotFoundPage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import ProtectedRoute from "@/components/ProtectedRoute";
import { AuthProvider } from "@/context/AuthContext";
import { useResponsive } from "@/hooks/useResponsive";

function AppRoutes() {
  const { isMobile } = useResponsive();

  const Layout = isMobile ? MobileLayout : MainLayout;

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects/new" element={<NewProjectPage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
          <Route path="/sessions/:sessionId" element={<SessionPage />} />
          <Route
            path="/sessions/:sessionId/replay"
            element={<ReplayPage />}
          />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/questions" element={<QuestionsPage />} />
          <Route path="/roles" element={<RolesPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </BrowserRouter>
  );
}
