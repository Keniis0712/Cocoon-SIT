import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  me: vi.fn(),
  buildSessionPatch: vi.fn(),
  updateMyProfile: vi.fn(),
  createImBindToken: vi.fn(),
  logout: vi.fn(),
  copyTextToClipboard: vi.fn(),
  showErrorToast: vi.fn(),
}));

vi.mock("@/api/user", () => ({
  buildSessionPatch: mocks.buildSessionPatch,
  createImBindToken: mocks.createImBindToken,
  logout: mocks.logout,
  me: mocks.me,
  updateMyProfile: mocks.updateMyProfile,
}));

vi.mock("@/api/client", () => ({
  showErrorToast: mocks.showErrorToast,
}));

vi.mock("@/lib/clipboard", () => ({
  copyTextToClipboard: mocks.copyTextToClipboard,
}));

vi.mock("@/lib/timezones", () => ({
  buildTimezoneOptions: () => [
    { value: "UTC", label: "UTC" },
    { value: "Asia/Shanghai", label: "Asia/Shanghai" },
  ],
  resolveBrowserTimezone: () => "Asia/Shanghai",
}));

vi.mock("sonner", () => ({
  toast: {
    success: vi.fn(),
  },
}));

vi.mock("@/components/PageFrame", () => ({
  default: ({
    title,
    description,
    children,
  }: {
    title: string;
    description?: string;
    children: React.ReactNode;
  }) => (
    <section>
      <h1>{title}</h1>
      <p>{description}</p>
      <div>{children}</div>
    </section>
  ),
}));

vi.mock("@/components/composes/PopupSelect", () => ({
  PopupSelect: ({
    value,
    onValueChange,
    options,
    placeholder,
  }: {
    value: string;
    onValueChange: (value: string) => void;
    options: Array<{ value: string; label: string }>;
    placeholder: string;
  }) => (
    <select
      aria-label={placeholder}
      value={value}
      onChange={(event) => onValueChange(event.target.value)}
    >
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
}));

import MePage from "@/pages/Me";
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

describe("MePage", () => {
  beforeEach(() => {
    seedUserStore();
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    mocks.me.mockResolvedValue({
      uid: "u-1",
      username: "alice",
      email: "alice@example.com",
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
      created_at: "2026-04-26T10:00:00Z",
    });
    mocks.buildSessionPatch.mockImplementation((profile: { timezone: string; username: string }) => ({
      timezone: profile.timezone,
      username: profile.username,
    }));
  });

  it("refreshes and renders the current profile", async () => {
    render(<MePage />);

    await waitFor(() => {
      expect(mocks.me).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByDisplayValue("alice@example.com")).toBeInTheDocument();
    expect(screen.getByDisplayValue("alice")).toBeInTheDocument();
  });

  it("saves timezone changes and copies generated bind tokens", async () => {
    mocks.updateMyProfile.mockResolvedValue({
      uid: "u-1",
      username: "alice",
      email: "alice@example.com",
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
      created_at: "2026-04-26T10:00:00Z",
    });
    mocks.createImBindToken.mockResolvedValue({
      token: "bind-token-1",
      expires_at: "2099-01-01T00:00:30Z",
      expires_in_seconds: 30,
    });
    mocks.copyTextToClipboard.mockResolvedValue(undefined);

    render(<MePage />);

    await screen.findByDisplayValue("alice@example.com");
    fireEvent.change(screen.getByLabelText("Asia/Shanghai"), {
      target: { value: "Asia/Shanghai" },
    });
    fireEvent.click(screen.getByRole("button", { name: /common.saveChanges/i }));

    await waitFor(() => {
      expect(mocks.updateMyProfile).toHaveBeenCalledWith({ timezone: "Asia/Shanghai" });
    });
    expect(useUserStore.getState().userInfo).toMatchObject({ timezone: "Asia/Shanghai" });

    fireEvent.click(screen.getByRole("button", { name: /me.imBindGenerate/i }));
    await waitFor(() => {
      expect(mocks.createImBindToken).toHaveBeenCalledTimes(1);
    });
    fireEvent.click(screen.getByRole("button", { name: /me.imBindCopy/i }));
    expect(mocks.copyTextToClipboard).toHaveBeenCalledWith("bind-token-1");
  });
});
