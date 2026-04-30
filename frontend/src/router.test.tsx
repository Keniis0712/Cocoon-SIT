import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RouterProvider, Outlet } from "react-router-dom";

vi.mock("@/components/MainLayout", () => ({
  default: () => (
    <div>
      <div>layout-shell</div>
      <Outlet />
    </div>
  ),
}));

vi.mock("@/pages/Login", () => ({
  default: () => <div>login-page</div>,
}));

vi.mock("@/pages/Cocoons", () => ({
  default: () => <div>cocoons-page</div>,
}));

function resetUserStore(
  store: { setState: (...args: any[]) => unknown; getState: () => Record<string, unknown> },
  isLoggedIn: boolean,
) {
  store.setState({
    userInfo: isLoggedIn
      ? {
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
          can_manage_system: true,
          can_manage_users: true,
          can_manage_prompts: true,
          can_manage_providers: true,
          timezone: "UTC",
          permissions: {},
          invite_quota_remaining: null,
          invite_quota_unlimited: true,
        }
      : null,
    isLoggedIn,
    login: store.getState().login,
    logout: store.getState().logout,
    updateInfo: store.getState().updateInfo,
    getToken: store.getState().getToken,
  });
}

describe("router guards", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    window.history.pushState({}, "", "/");
  });

  it("redirects unauthenticated protected routes to login", async () => {
    window.history.pushState({}, "", "/cocoons");

    const { useUserStore } = await import("@/store/useUserStore");
    resetUserStore(useUserStore, false);

    const { router } = await import("@/router");
    render(<RouterProvider router={router} />);

    expect(await screen.findByText("login-page")).toBeInTheDocument();
    expect(screen.queryByText("cocoons-page")).not.toBeInTheDocument();
  });

  it("redirects logged-in users away from login", async () => {
    window.history.pushState({}, "", "/login");

    const { useUserStore } = await import("@/store/useUserStore");
    resetUserStore(useUserStore, true);

    const { router } = await import("@/router");
    render(<RouterProvider router={router} />);

    await waitFor(() => {
      expect(screen.getByText("layout-shell")).toBeInTheDocument();
    });
    expect(screen.getByText("cocoons-page")).toBeInTheDocument();
    expect(screen.queryByText("login-page")).not.toBeInTheDocument();
  });
});
