"use client";

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Binary,
  BarChart3,
  BrainCircuit,
  Puzzle,
  MessagesSquare,
  FileCode2,
  FileSearch,
  FolderTree,
  GitMerge,
  KeyRound,
  BellRing,
  Tags,
  Settings2,
  ShieldCheck,
  Users,
} from "lucide-react";

import { NavMain } from "@/components/nav-main";
import { NavSecondary } from "@/components/nav-secondary";
import { NavUser } from "@/components/nav-user";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarRail,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { hasAnyPermission } from "@/lib/permissions";
import { useUserStore } from "@/store/useUserStore";

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { t } = useTranslation(["nav", "wakeups"]);
  const userInfo = useUserStore((state) => state.userInfo);

  const workspaceItems = [
    hasAnyPermission(userInfo, ["cocoons:read", "cocoons:write"])
      ? { title: t("cocoons"), url: "/cocoons", icon: <BrainCircuit /> }
      : null,
    hasAnyPermission(userInfo, ["cocoons:read", "cocoons:write"])
      ? { title: t("chatGroups"), url: "/chat-groups", icon: <MessagesSquare /> }
      : null,
    hasAnyPermission(userInfo, ["characters:read", "characters:write"])
      ? { title: t("characters"), url: "/characters", icon: <Users /> }
      : null,
    hasAnyPermission(userInfo, ["merges:write"])
      ? { title: t("merges"), url: "/merges", icon: <GitMerge /> }
      : null,
    hasAnyPermission(userInfo, ["tags:read", "tags:write"])
      ? { title: t("tags"), url: "/tags", icon: <Tags /> }
      : null,
    { title: t("plugins"), url: "/plugins", icon: <Puzzle /> },
  ].filter(Boolean) as { title: string; url: string; icon: ReactNode }[];

  const collaborationItems = [
    hasAnyPermission(userInfo, ["users:read", "users:write"])
      ? { title: t("groups"), url: "/groups", icon: <FolderTree /> }
      : null,
    hasAnyPermission(userInfo, ["users:read", "users:write"])
      ? { title: t("invites"), url: "/invites", icon: <KeyRound /> }
      : null,
  ].filter(Boolean) as { title: string; url: string; icon: ReactNode }[];

  const managementItems = [
    hasAnyPermission(userInfo, ["users:read", "users:write"])
      ? { title: t("users"), url: "/users", icon: <Users /> }
      : null,
    hasAnyPermission(userInfo, ["providers:read", "providers:write"])
      ? { title: t("providers"), url: "/providers", icon: <Binary /> }
      : null,
    hasAnyPermission(userInfo, ["prompt_templates:read", "prompt_templates:write"])
      ? { title: t("prompts"), url: "/prompt-templates", icon: <FileCode2 /> }
      : null,
    hasAnyPermission(userInfo, ["providers:read", "providers:write"])
      ? { title: t("embeddingProviders"), url: "/embedding-providers", icon: <Binary /> }
      : null,
    hasAnyPermission(userInfo, ["audits:read"])
      ? { title: t("audits"), url: "/audits", icon: <FileSearch /> }
      : null,
    hasAnyPermission(userInfo, ["audits:read"])
      ? { title: t("wakeups:title"), url: "/wakeups", icon: <BellRing /> }
      : null,
    hasAnyPermission(userInfo, ["insights:read"])
      ? { title: t("insights"), url: "/insights", icon: <BarChart3 /> }
      : null,
    hasAnyPermission(userInfo, ["plugins:read", "plugins:write", "plugins:run"])
      ? { title: t("pluginsAdmin"), url: "/admin/plugins", icon: <Puzzle /> }
      : null,
    userInfo?.can_manage_system
      ? { title: t("settings"), url: "/settings", icon: <Settings2 /> }
      : null,
  ].filter(Boolean) as { title: string; url: string; icon: ReactNode }[];

  const secondaryItems = [{ title: t("me"), url: "/me", icon: <ShieldCheck /> }];

  return (
    <Sidebar className="border-r-0" variant="inset" {...props}>
      <SidebarHeader className="gap-4 px-3 py-4">
        <div className="rounded-2xl border border-sidebar-border bg-sidebar-accent/60 p-4">
          <div className="mb-3 flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground">
              <BrainCircuit className="size-5" />
            </div>
            <div>
              <div className="font-heading text-sm font-semibold">Cocoon-SIT</div>
              <div className="text-xs text-sidebar-foreground/70">{t("subtitle")}</div>
            </div>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("workspace")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <NavMain items={workspaceItems} />
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>{t("collaboration")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <NavMain items={collaborationItems} />
          </SidebarGroupContent>
        </SidebarGroup>
        {managementItems.length > 0 ? (
          <SidebarGroup>
            <SidebarGroupLabel>{t("management")}</SidebarGroupLabel>
            <SidebarGroupContent>
              <NavMain items={managementItems} />
            </SidebarGroupContent>
          </SidebarGroup>
        ) : null}
        <SidebarSeparator />
        <NavSecondary items={secondaryItems} className="mt-auto" />
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  );
}
