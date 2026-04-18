"use client";

import { ChevronsUpDown, Languages, LogOut, UserCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";

import { logout } from "@/api/user";
import { useUserStore } from "@/store/useUserStore";

export function NavUser() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const { isMobile } = useSidebar();
  const logoutStore = useUserStore((state) => state.logout);
  const refreshToken = useUserStore((state) => state.userInfo?.refresh_token);
  const userInfo = useUserStore((state) => state.userInfo)!;

  async function handleLogout() {
    try {
      if (refreshToken) {
        await logout(refreshToken);
      }
    } catch {
      // Ignore logout request failures and clear local state anyway.
    } finally {
      logoutStore();
      toast.success(t("nav.logoutSuccess"));
      navigate("/login", { replace: true });
    }
  }

  function toggleLanguage() {
    void i18n.changeLanguage(i18n.resolvedLanguage === "zh" ? "en" : "zh");
  }

  return (
    <SidebarMenu>
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
            >
              <UserCircle2 className="size-5" />
              <div className="grid flex-1 text-left text-sm leading-tight">
                <span className="truncate font-medium">{userInfo.username}</span>
                <span className="truncate text-xs">
                  {userInfo.role} · uid: {userInfo.uid}
                </span>
              </div>
              <ChevronsUpDown className="ml-auto size-4" />
            </SidebarMenuButton>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
            side={isMobile ? "bottom" : "right"}
            align="end"
            sideOffset={4}
          >
            <DropdownMenuLabel className="p-0 font-normal">
              <div className="flex items-center gap-2 px-1 py-1.5 text-left text-sm">
                <div className="grid flex-1 text-left text-sm leading-tight">
                  <span className="truncate font-medium">{userInfo.username}</span>
                  <span className="truncate text-xs">
                    {userInfo.role} · uid: {userInfo.uid}
                  </span>
                </div>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate("/me")}>
              <UserCircle2 />
              {t("nav.accountCenter")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={toggleLanguage}>
              <Languages />
              {t("nav.switchLanguage")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut />
              {t("nav.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
