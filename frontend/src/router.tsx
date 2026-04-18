import type { ReactNode } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";

import MainLayout from "@/components/MainLayout";
import AuditsWorkbenchPage from "@/pages/AuditsWorkbench";
import CharactersPage from "@/pages/Characters";
import ChatGroupsPage from "@/pages/ChatGroupsPage";
import CocoonMemoryPage from "@/pages/CocoonMemoryPage";
import CocoonWorkspacePage from "@/pages/CocoonWorkspace";
import CocoonsPage from "@/pages/Cocoons";
import EmbeddingProvidersPage from "@/pages/EmbeddingProvidersPage";
import GroupsPage from "@/pages/Groups";
import InsightsPage from "@/pages/Insights";
import InvitesPage from "@/pages/Invites";
import LoginPage from "@/pages/Login";
import MePage from "@/pages/Me";
import MergesPage from "@/pages/Merges";
import ProvidersPage from "@/pages/Providers";
import SettingsPage from "@/pages/Settings";
import TagsPage from "@/pages/TagsPage";
import UsersPage from "@/pages/Users";
import { useUserStore } from "@/store/useUserStore";

function ProtectedRoute({ children }: { children: ReactNode }) {
  const isLoggedIn = useUserStore((state) => state.isLoggedIn);
  return isLoggedIn ? <>{children}</> : <Navigate to="/login" replace />;
}

function LoginRoute({ children }: { children: ReactNode }) {
  const isLoggedIn = useUserStore((state) => state.isLoggedIn);
  return isLoggedIn ? <Navigate to="/cocoons" replace /> : <>{children}</>;
}

export const router = createBrowserRouter([
  { path: "/", element: <Navigate to="/cocoons" replace /> },
  {
    path: "/login",
    element: (
      <LoginRoute>
        <LoginPage />
      </LoginRoute>
    ),
  },
  {
    element: (
      <ProtectedRoute>
        <MainLayout />
      </ProtectedRoute>
    ),
    children: [
      { path: "/cocoons", element: <CocoonsPage /> },
      { path: "/cocoons/:cocoonId", element: <CocoonWorkspacePage /> },
      { path: "/cocoons/:cocoonId/memories", element: <CocoonMemoryPage /> },
      { path: "/chat-groups", element: <ChatGroupsPage /> },
      { path: "/tags", element: <TagsPage /> },
      { path: "/characters", element: <CharactersPage /> },
      { path: "/groups", element: <GroupsPage /> },
      { path: "/invites", element: <InvitesPage /> },
      { path: "/merges", element: <MergesPage /> },
      { path: "/providers", element: <ProvidersPage /> },
      { path: "/embedding-providers", element: <EmbeddingProvidersPage /> },
      { path: "/users", element: <UsersPage /> },
      { path: "/audits", element: <AuditsWorkbenchPage /> },
      { path: "/insights", element: <InsightsPage /> },
      { path: "/settings", element: <SettingsPage /> },
      { path: "/me", element: <MePage /> },
    ],
  },
]);
