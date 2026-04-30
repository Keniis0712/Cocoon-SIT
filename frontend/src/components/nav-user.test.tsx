import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  logout: vi.fn(),
  toastSuccess: vi.fn(),
  changeAppLanguage: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => mocks.navigate,
}));

vi.mock("sonner", () => ({
  toast: {
    success: mocks.toastSuccess,
  },
}));

vi.mock("@/api/user", () => ({
  logout: mocks.logout,
}));

vi.mock("@/i18n", () => ({
  changeAppLanguage: mocks.changeAppLanguage,
}));

vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuLabel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  DropdownMenuSeparator: () => <hr />,
  DropdownMenuItem: ({
    children,
    onClick,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
  }) => (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  ),
}));

vi.mock("@/components/ui/sidebar", () => ({
  SidebarMenu: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SidebarMenuButton: ({ children }: { children: React.ReactNode }) => <button type="button">{children}</button>,
  SidebarMenuItem: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useSidebar: () => ({ isMobile: false }),
}));

import { NavUser } from "@/components/nav-user";
import { useUserStore } from "@/store/useUserStore";

function seedUserStore() {
  useUserStore.setState({
    userInfo: {
      access_token: "token",
      refresh_token: "refresh-token",
      token_type: "bearer",
      expires_in_seconds: 3600,
      uid: "u-1",
      username: "alice",
      parent_uid: null,
      user_path: null,
      role: "admin",
      role_level: 0,
      can_audit: true,
      can_manage_system: true,
      can_manage_users: true,
      can_manage_prompts: true,
      can_manage_providers: true,
      timezone: "UTC",
      permissions: {},
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

describe("NavUser", () => {
  beforeEach(() => {
    seedUserStore();
    mocks.navigate.mockReset();
    mocks.logout.mockReset();
    mocks.toastSuccess.mockReset();
    mocks.changeAppLanguage.mockReset();
  });

  it("navigates to the account center and toggles language", () => {
    render(<NavUser />);

    fireEvent.click(screen.getByRole("button", { name: /nav.accountCenter/i }));
    fireEvent.click(screen.getByRole("button", { name: /nav.switchLanguage/i }));

    expect(mocks.navigate).toHaveBeenCalledWith("/me");
    expect(mocks.changeAppLanguage).toHaveBeenCalledWith("zh");
  });

  it("logs out remotely when a refresh token exists, then clears local state", async () => {
    mocks.logout.mockResolvedValue(undefined);

    render(<NavUser />);

    fireEvent.click(screen.getByRole("button", { name: /nav.logout/i }));

    await waitFor(() => {
      expect(mocks.logout).toHaveBeenCalledWith("refresh-token");
    });
    expect(useUserStore.getState().isLoggedIn).toBe(false);
    expect(mocks.toastSuccess).toHaveBeenCalledWith("nav.logoutSuccess");
    expect(mocks.navigate).toHaveBeenCalledWith("/login", { replace: true });
  });
});
