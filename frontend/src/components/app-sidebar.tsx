"use client";

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import {
  Binary,
  BarChart3,
  BrainCircuit,
  MessagesSquare,
  FileCode2,
  FileSearch,
  FolderTree,
  GitMerge,
  KeyRound,
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
  const { t } = useTranslation();
  const userInfo = useUserStore((state) => state.userInfo);

  const workspaceItems = [
    hasAnyPermission(userInfo, ["cocoons:read", "cocoons:write"])
      ? { title: t("nav.cocoons"), url: "/cocoons", icon: <BrainCircuit /> }
      : null,
    hasAnyPermission(userInfo, ["cocoons:read", "cocoons:write"])
      ? { title: t("nav.chatGroups"), url: "/chat-groups", icon: <MessagesSquare /> }
      : null,
    hasAnyPermission(userInfo, ["characters:read", "characters:write"])
      ? { title: t("nav.characters"), url: "/characters", icon: <Users /> }
      : null,
    hasAnyPermission(userInfo, ["merges:write"])
      ? { title: t("nav.merges"), url: "/merges", icon: <GitMerge /> }
      : null,
    hasAnyPermission(userInfo, ["tags:read", "tags:write"])
      ? { title: t("nav.tags"), url: "/tags", icon: <Tags /> }
      : null,
  ].filter(Boolean) as { title: string; url: string; icon: ReactNode }[];

  const collaborationItems = [
    hasAnyPermission(userInfo, ["users:read", "users:write"])
      ? { title: t("nav.groups"), url: "/groups", icon: <FolderTree /> }
      : null,
    hasAnyPermission(userInfo, ["users:read", "users:write"])
      ? { title: t("nav.invites"), url: "/invites", icon: <KeyRound /> }
      : null,
  ].filter(Boolean) as { title: string; url: string; icon: ReactNode }[];

  const managementItems = [
    hasAnyPermission(userInfo, ["users:read", "users:write"])
      ? { title: t("nav.users"), url: "/users", icon: <Users /> }
      : null,
    hasAnyPermission(userInfo, ["providers:read", "providers:write"])
      ? { title: t("nav.providers"), url: "/providers", icon: <Binary /> }
      : null,
    hasAnyPermission(userInfo, ["prompt_templates:read", "prompt_templates:write"])
      ? { title: t("nav.prompts"), url: "/prompt-templates", icon: <FileCode2 /> }
      : null,
    hasAnyPermission(userInfo, ["providers:read", "providers:write"])
      ? { title: t("nav.embeddingProviders"), url: "/embedding-providers", icon: <Binary /> }
      : null,
    hasAnyPermission(userInfo, ["audits:read"])
      ? { title: t("nav.audits"), url: "/audits", icon: <FileSearch /> }
      : null,
    hasAnyPermission(userInfo, ["insights:read"])
      ? { title: t("nav.insights"), url: "/insights", icon: <BarChart3 /> }
      : null,
    hasAnyPermission(userInfo, ["artifacts:cleanup", "roles:write", "prompt_templates:write"])
      ? { title: t("nav.settings"), url: "/settings", icon: <Settings2 /> }
      : null,
  ].filter(Boolean) as { title: string; url: string; icon: ReactNode }[];

  const secondaryItems = [{ title: t("nav.me"), url: "/me", icon: <ShieldCheck /> }];

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
              <div className="text-xs text-sidebar-foreground/70">{t("nav.subtitle")}</div>
            </div>
          </div>
        </div>
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("nav.workspace")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <NavMain items={workspaceItems} />
          </SidebarGroupContent>
        </SidebarGroup>
        <SidebarGroup>
          <SidebarGroupLabel>{t("nav.collaboration")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <NavMain items={collaborationItems} />
          </SidebarGroupContent>
        </SidebarGroup>
        {managementItems.length > 0 ? (
          <SidebarGroup>
            <SidebarGroupLabel>{t("nav.management")}</SidebarGroupLabel>
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
