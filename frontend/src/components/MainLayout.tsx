import { useEffect } from "react";
import { Outlet } from "react-router-dom";

import { buildSessionPatch, me } from "@/api/user";
import { AppSidebar } from "@/components/app-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { useUserStore } from "@/store/useUserStore";

export default function MainLayout() {
  const userInfo = useUserStore((state) => state.userInfo);
  const updateInfo = useUserStore((state) => state.updateInfo);

  useEffect(() => {
    async function refreshSession() {
      if (!userInfo?.uid) {
        return;
      }
      try {
        const profile = await me();
        updateInfo(buildSessionPatch(profile));
      } catch {
        // Let the shared API client handle unauthorized redirects.
      }
    }

    void refreshSession();
  }, [updateInfo, userInfo?.access_token, userInfo?.uid]);

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(14,116,144,0.08),_transparent_30%),radial-gradient(circle_at_bottom_right,_rgba(190,24,93,0.08),_transparent_28%)]">
      <SidebarProvider>
        <AppSidebar />
        <SidebarInset className="min-h-screen">
          <Outlet />
        </SidebarInset>
      </SidebarProvider>
    </div>
  );
}
