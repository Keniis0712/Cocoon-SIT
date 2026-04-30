import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  me: vi.fn(),
  buildSessionPatch: vi.fn(),
}));

vi.mock("@/api/user", () => ({
  me: mocks.me,
  buildSessionPatch: mocks.buildSessionPatch,
}));

vi.mock("@/components/app-sidebar", () => ({
  AppSidebar: () => <div>sidebar-shell</div>,
}));

vi.mock("@/components/ui/sidebar", () => ({
  SidebarInset: ({ children, className }: { children: React.ReactNode; className?: string }) => (
    <div data-testid="sidebar-inset" className={className}>
      {children}
    </div>
  ),
  SidebarProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock("react-router-dom", () => ({
  Outlet: () => <div>outlet-content</div>,
}));

import MainLayout from "@/components/MainLayout";
import { useUserStore } from "@/store/useUserStore";

function resetUserStore(userInfo: Record<string, unknown> | null) {
  useUserStore.setState({
    userInfo: userInfo as never,
    isLoggedIn: Boolean(userInfo),
    login: useUserStore.getState().login,
    logout: useUserStore.getState().logout,
    updateInfo: useUserStore.getState().updateInfo,
    getToken: useUserStore.getState().getToken,
  });
}

describe("MainLayout", () => {
  beforeEach(() => {
    mocks.me.mockReset();
    mocks.buildSessionPatch.mockReset();
  });

  it("refreshes the session profile when a logged-in user is present", async () => {
    resetUserStore({
      access_token: "token",
      uid: "u-1",
      username: "alice",
    });
    mocks.me.mockResolvedValue({
      uid: "u-1",
      username: "alice-updated",
      timezone: "Asia/Shanghai",
    });
    mocks.buildSessionPatch.mockReturnValue({
      username: "alice-updated",
      timezone: "Asia/Shanghai",
    });

    render(<MainLayout />);

    expect(screen.getByText("sidebar-shell")).toBeInTheDocument();
    expect(screen.getByText("outlet-content")).toBeInTheDocument();

    await waitFor(() => {
      expect(mocks.me).toHaveBeenCalledTimes(1);
    });
    expect(mocks.buildSessionPatch).toHaveBeenCalledWith({
      uid: "u-1",
      username: "alice-updated",
      timezone: "Asia/Shanghai",
    });
    expect(useUserStore.getState().userInfo).toMatchObject({
      username: "alice-updated",
      timezone: "Asia/Shanghai",
    });
  });

  it("skips profile refresh when no session user exists", () => {
    resetUserStore(null);

    render(<MainLayout />);

    expect(mocks.me).not.toHaveBeenCalled();
  });
});
