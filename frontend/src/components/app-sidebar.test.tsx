import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

vi.mock("react-router-dom", () => ({
  NavLink: ({
    to,
    children,
  }: {
    to: string;
    children: (args: { isActive: boolean }) => React.ReactNode;
  }) => <a href={to}>{children({ isActive: false })}</a>,
}));

vi.mock("@/components/nav-secondary", () => ({
  NavSecondary: ({ items }: { items: Array<{ title: string }> }) => (
    <div>{items.map((item) => item.title).join(",")}</div>
  ),
}));

vi.mock("@/components/nav-user", () => ({
  NavUser: () => <div>nav-user</div>,
}));

vi.mock("@/components/ui/sidebar", () => ({
  Sidebar: ({ children }: { children: React.ReactNode }) => <aside>{children}</aside>,
  SidebarContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarFooter: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarGroup: ({ children }: { children: React.ReactNode }) => <section>{children}</section>,
  SidebarGroupContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarGroupLabel: ({ children }: { children: React.ReactNode }) => <h2>{children}</h2>,
  SidebarHeader: ({ children }: { children: React.ReactNode }) => <header>{children}</header>,
  SidebarRail: () => <div>sidebar-rail</div>,
  SidebarSeparator: () => <hr />,
  SidebarMenu: ({ children }: { children: React.ReactNode }) => <ul>{children}</ul>,
  SidebarMenuButton: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => <li>{children}</li>,
}));

import { AppSidebar } from "@/components/app-sidebar";
import { useUserStore } from "@/store/useUserStore";

function resetUserStore(permissions: Record<string, boolean>, canManageSystem = false) {
  useUserStore.setState({
    userInfo: {
      access_token: "token",
      refresh_token: "refresh",
      token_type: "bearer",
      expires_in_seconds: 3600,
      uid: "u-1",
      username: "alice",
      parent_uid: null,
      user_path: null,
      role: "admin",
      role_level: 0,
      can_audit: true,
      can_manage_system: canManageSystem,
      can_manage_users: true,
      can_manage_prompts: true,
      can_manage_providers: true,
      timezone: "UTC",
      permissions,
      invite_quota_remaining: null,
      invite_quota_unlimited: true,
    },
    isLoggedIn: true,
    login: useUserStore.getState().login,
    logout: useUserStore.getState().logout,
    updateInfo: useUserStore.getState().updateInfo,
    getToken: useUserStore.getState().getToken,
  });
}

describe("AppSidebar", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("shows permission-gated navigation items", () => {
    resetUserStore({
      "cocoons:read": true,
      "characters:read": true,
      "merges:write": true,
      "tags:read": true,
      "tags:write": true,
      "providers:read": true,
      "providers:write": true,
      "prompt_templates:read": true,
      "audits:read": true,
      "insights:read": true,
      "plugins:read": true,
      "users:read": true,
      "users:write": true,
    }, true);

    render(<AppSidebar />);

    expect(screen.getByText("workspace")).toBeInTheDocument();
    expect(screen.getByText("cocoons")).toBeInTheDocument();
    expect(screen.getByText("chatGroups")).toBeInTheDocument();
    expect(screen.getByText("pluginsAdmin")).toBeInTheDocument();
    expect(screen.getByText("settings")).toBeInTheDocument();
    expect(screen.getByText("me")).toBeInTheDocument();
  });

  it("hides management items when permissions are absent", () => {
    resetUserStore({});

    render(<AppSidebar />);

    expect(screen.getByText("plugins")).toBeInTheDocument();
    expect(screen.queryByText("users")).not.toBeInTheDocument();
    expect(screen.queryByText("providers")).not.toBeInTheDocument();
    expect(screen.queryByText("settings")).not.toBeInTheDocument();
  });
});
