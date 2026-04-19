import { Suspense, lazy, type ComponentType, type ReactNode } from "react";
import { Navigate, createBrowserRouter } from "react-router-dom";

import { useUserStore } from "@/store/useUserStore";

const MainLayout = lazy(() => import("@/components/MainLayout"));
const AuditsWorkbenchPage = lazy(() => import("@/pages/AuditsWorkbench"));
const CharactersPage = lazy(() => import("@/pages/Characters"));
const ChatGroupsPage = lazy(() => import("@/pages/ChatGroupsPage"));
const ChatGroupWorkspacePage = lazy(() => import("@/pages/ChatGroupWorkspace"));
const CocoonMemoryPage = lazy(() => import("@/pages/CocoonMemoryPage"));
const CocoonWorkspacePage = lazy(() => import("@/pages/CocoonWorkspace"));
const CocoonsPage = lazy(() => import("@/pages/Cocoons"));
const EmbeddingProvidersPage = lazy(() => import("@/pages/EmbeddingProvidersPage"));
const GroupsPage = lazy(() => import("@/pages/Groups"));
const InsightsPage = lazy(() => import("@/pages/Insights"));
const InvitesPage = lazy(() => import("@/pages/Invites"));
const LoginPage = lazy(() => import("@/pages/Login"));
const MePage = lazy(() => import("@/pages/Me"));
const MergesPage = lazy(() => import("@/pages/Merges"));
const ProvidersPage = lazy(() => import("@/pages/Providers"));
const PromptTemplatesPage = lazy(() => import("@/pages/PromptTemplates"));
const SettingsPage = lazy(() => import("@/pages/Settings"));
const TagsPage = lazy(() => import("@/pages/TagsPage"));
const UsersPage = lazy(() => import("@/pages/Users"));

function RouteFallback() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center px-6 text-sm text-muted-foreground">
      Loading page...
    </div>
  );
}

function renderLazyPage(Component: ComponentType) {
  return (
    <Suspense fallback={<RouteFallback />}>
      <Component />
    </Suspense>
  );
}

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
    element: <LoginRoute>{renderLazyPage(LoginPage)}</LoginRoute>,
  },
  {
    element: <ProtectedRoute>{renderLazyPage(MainLayout)}</ProtectedRoute>,
    children: [
      { path: "/cocoons", element: renderLazyPage(CocoonsPage) },
      { path: "/cocoons/:cocoonId", element: renderLazyPage(CocoonWorkspacePage) },
      { path: "/cocoons/:cocoonId/memory", element: renderLazyPage(CocoonMemoryPage) },
      { path: "/cocoons/:cocoonId/memories", element: renderLazyPage(CocoonMemoryPage) },
      { path: "/chat-groups", element: renderLazyPage(ChatGroupsPage) },
      { path: "/chat-groups/:roomId", element: renderLazyPage(ChatGroupWorkspacePage) },
      { path: "/tags", element: renderLazyPage(TagsPage) },
      { path: "/characters", element: renderLazyPage(CharactersPage) },
      { path: "/groups", element: renderLazyPage(GroupsPage) },
      { path: "/invites", element: renderLazyPage(InvitesPage) },
      { path: "/merges", element: renderLazyPage(MergesPage) },
      { path: "/providers", element: renderLazyPage(ProvidersPage) },
      { path: "/prompt-templates", element: renderLazyPage(PromptTemplatesPage) },
      { path: "/embedding-providers", element: renderLazyPage(EmbeddingProvidersPage) },
      { path: "/users", element: renderLazyPage(UsersPage) },
      { path: "/audits", element: renderLazyPage(AuditsWorkbenchPage) },
      { path: "/insights", element: renderLazyPage(InsightsPage) },
      { path: "/settings", element: renderLazyPage(SettingsPage) },
      { path: "/me", element: renderLazyPage(MePage) },
    ],
  },
]);
