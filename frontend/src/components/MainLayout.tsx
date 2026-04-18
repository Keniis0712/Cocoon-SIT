import { Outlet } from "react-router-dom";

import { AppSidebar } from "@/components/app-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export default function MainLayout() {
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
