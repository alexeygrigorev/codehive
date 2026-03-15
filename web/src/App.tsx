import { BrowserRouter, Routes, Route } from "react-router-dom";
import MainLayout from "@/layouts/MainLayout";
import MobileLayout from "@/layouts/MobileLayout";
import DashboardPage from "@/pages/DashboardPage";
import ProjectPage from "@/pages/ProjectPage";
import SessionPage from "@/pages/SessionPage";
import QuestionsPage from "@/pages/QuestionsPage";
import ReplayPage from "@/pages/ReplayPage";
import RolesPage from "@/pages/RolesPage";
import NotFoundPage from "@/pages/NotFoundPage";
import { useResponsive } from "@/hooks/useResponsive";

export default function App() {
  const { isMobile } = useResponsive();

  const Layout = isMobile ? MobileLayout : MainLayout;

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
          <Route path="/sessions/:sessionId" element={<SessionPage />} />
          <Route path="/sessions/:sessionId/replay" element={<ReplayPage />} />
          <Route path="/questions" element={<QuestionsPage />} />
          <Route path="/roles" element={<RolesPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
