import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "@/pages/Login";
import { useUserStore } from "@/store/useUserStore";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  login: vi.fn(),
  register: vi.fn(),
  getPublicFeatures: vi.fn(),
  setTheme: vi.fn(),
  changeAppLanguage: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock("@/api/user", () => ({
  login: mocks.login,
  register: mocks.register,
  getPublicFeatures: mocks.getPublicFeatures,
}));

vi.mock("@/api/client", () => ({
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
}));

vi.mock("@/hooks/use-theme", () => ({
  useTheme: () => ({
    theme: "light",
    setTheme: mocks.setTheme,
  }),
}));

vi.mock("@/i18n", () => ({
  changeAppLanguage: mocks.changeAppLanguage,
}));

vi.mock("@/lib/timezones", () => ({
  resolveBrowserTimezone: () => "Asia/Shanghai",
}));

function sessionUser(overrides: Record<string, unknown> = {}) {
  return {
    access_token: "access",
    refresh_token: "refresh",
    token_type: "bearer" as const,
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
    timezone: "Asia/Shanghai",
    permissions: {},
    invite_quota_remaining: null,
    invite_quota_unlimited: true,
    ...overrides,
  };
}

function resetUserStore() {
  useUserStore.setState({
    userInfo: null,
    isLoggedIn: false,
    login: useUserStore.getState().login,
    logout: useUserStore.getState().logout,
    updateInfo: useUserStore.getState().updateInfo,
    getToken: useUserStore.getState().getToken,
  });
}

describe("LoginPage", () => {
  beforeEach(() => {
    mocks.navigate.mockReset();
    mocks.login.mockReset();
    mocks.register.mockReset();
    mocks.getPublicFeatures.mockReset();
    mocks.setTheme.mockReset();
    mocks.changeAppLanguage.mockReset();
    window.localStorage.clear();
    resetUserStore();
  });

  it("logs users in and redirects to the cocoon workspace", async () => {
    mocks.getPublicFeatures.mockResolvedValue({ allow_registration: false });
    mocks.login.mockResolvedValue(sessionUser());

    render(<LoginPage />);

    fireEvent.change(await screen.findByLabelText("login.placeholderUser"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByLabelText("login.placeholderPass"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "login.submit" }));

    await waitFor(() => {
      expect(mocks.login).toHaveBeenCalledWith("alice", "secret");
    });
    expect(useUserStore.getState().isLoggedIn).toBe(true);
    expect(useUserStore.getState().userInfo?.username).toBe("alice");
    expect(mocks.navigate).toHaveBeenCalledWith("/cocoons", { replace: true });
  });

  it("submits registration payloads with invite code and browser timezone", async () => {
    mocks.getPublicFeatures.mockResolvedValue({ allow_registration: true });
    mocks.register.mockResolvedValue(sessionUser({ username: "new-user" }));

    render(<LoginPage />);

    fireEvent.click(await screen.findByRole("button", { name: "login.modeRegister" }));
    fireEvent.change(screen.getByLabelText("login.placeholderUser"), {
      target: { value: "new-user" },
    });
    fireEvent.change(screen.getByLabelText("common.email"), {
      target: { value: "new@example.com" },
    });
    fireEvent.change(screen.getByLabelText("login.inviteCode"), {
      target: { value: "INVITE-123" },
    });
    fireEvent.change(screen.getByLabelText("login.placeholderPass"), {
      target: { value: "super-secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "login.registerSubmit" }));

    await waitFor(() => {
      expect(mocks.register).toHaveBeenCalledWith({
        username: "new-user",
        password: "super-secret",
        email: "new@example.com",
        invite_code: "INVITE-123",
        timezone: "Asia/Shanghai",
      });
    });
    expect(useUserStore.getState().userInfo?.username).toBe("new-user");
    expect(mocks.navigate).toHaveBeenCalledWith("/cocoons", { replace: true });
  });

  it("shows API errors without redirecting", async () => {
    mocks.getPublicFeatures.mockResolvedValue({ allow_registration: false });
    mocks.login.mockRejectedValue(new Error("Bad credentials"));

    render(<LoginPage />);

    fireEvent.change(await screen.findByLabelText("login.placeholderUser"), {
      target: { value: "alice" },
    });
    fireEvent.change(screen.getByLabelText("login.placeholderPass"), {
      target: { value: "wrong-pass" },
    });
    fireEvent.click(screen.getByRole("button", { name: "login.submit" }));

    expect(await screen.findByText("Bad credentials")).toBeInTheDocument();
    expect(useUserStore.getState().isLoggedIn).toBe(false);
    expect(mocks.navigate).not.toHaveBeenCalled();
  });
});
