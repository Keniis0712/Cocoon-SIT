import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import AdminPluginsPage from "@/pages/AdminPlugins";
import type {
  AdminPluginDetailRead,
  AdminPluginEventRead,
  AdminPluginListItemRead,
} from "@/api/types/plugins";
import { useUserStore } from "@/store/useUserStore";

const mocks = vi.hoisted(() => ({
  listAdminPlugins: vi.fn(),
  getAdminPlugin: vi.fn(),
  listAdminPluginGroupVisibility: vi.fn(),
  listAdminPluginSharedPackages: vi.fn(),
  listGroups: vi.fn(),
  updateAdminPluginConfig: vi.fn(),
  deleteAdminPlugin: vi.fn(),
  installAdminPlugin: vi.fn(),
  setAdminPluginEnabled: vi.fn(),
  setAdminPluginEventEnabled: vi.fn(),
  setAdminPluginGlobalVisibility: vi.fn(),
  setAdminPluginGroupVisibility: vi.fn(),
  runAdminPluginEventNow: vi.fn(),
  updateAdminPlugin: vi.fn(),
  validateAdminPluginConfig: vi.fn(),
  updateAdminPluginEventConfig: vi.fn(),
  updateAdminPluginEventSchedule: vi.fn(),
  showErrorToast: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/api/admin-plugins", () => ({
  deleteAdminPlugin: mocks.deleteAdminPlugin,
  getAdminPlugin: mocks.getAdminPlugin,
  installAdminPlugin: mocks.installAdminPlugin,
  listAdminPluginGroupVisibility: mocks.listAdminPluginGroupVisibility,
  listAdminPluginSharedPackages: mocks.listAdminPluginSharedPackages,
  listAdminPlugins: mocks.listAdminPlugins,
  setAdminPluginEnabled: mocks.setAdminPluginEnabled,
  setAdminPluginEventEnabled: mocks.setAdminPluginEventEnabled,
  setAdminPluginGlobalVisibility: mocks.setAdminPluginGlobalVisibility,
  setAdminPluginGroupVisibility: mocks.setAdminPluginGroupVisibility,
  runAdminPluginEventNow: mocks.runAdminPluginEventNow,
  updateAdminPlugin: mocks.updateAdminPlugin,
  updateAdminPluginConfig: mocks.updateAdminPluginConfig,
  validateAdminPluginConfig: mocks.validateAdminPluginConfig,
  updateAdminPluginEventConfig: mocks.updateAdminPluginEventConfig,
  updateAdminPluginEventSchedule: mocks.updateAdminPluginEventSchedule,
}));

vi.mock("@/api/groups", () => ({
  listGroups: mocks.listGroups,
}));

vi.mock("@/api/client", () => ({
  showErrorToast: mocks.showErrorToast,
}));

vi.mock("sonner", () => ({
  toast: {
    success: mocks.toastSuccess,
    error: mocks.toastError,
  },
}));

vi.mock("@/components/PageFrame", () => ({
  default: ({
    title,
    description,
    actions,
    children,
  }: {
    title: string;
    description: string;
    actions?: React.ReactNode;
    children: React.ReactNode;
  }) => (
    <section>
      <h1>{title}</h1>
      <p>{description}</p>
      <div>{actions}</div>
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
      <option value="">{placeholder}</option>
      {options.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </select>
  ),
}));

function resetUserStore(permissions: Record<string, boolean>) {
  useUserStore.setState({
    userInfo: {
      access_token: "token",
      refresh_token: "refresh",
      token_type: "bearer",
      expires_in_seconds: 3600,
      uid: "u-1",
      username: "admin",
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

function adminPluginListItem(
  overrides: Partial<AdminPluginListItemRead> = {},
): AdminPluginListItemRead {
  return {
    id: "admin-plugin-1",
    name: "ops-admin",
    display_name: "Ops Admin",
    plugin_type: "external",
    entry_module: "plugins.ops_admin",
    service_function_name: "run",
    status: "enabled",
    install_source: "upload",
    data_dir: "plugins/data",
    config_schema_json: {},
    default_config_json: {},
    config_json: { retries: 3 },
    user_config_schema_json: {},
    user_default_config_json: {},
    settings_validation_function_name: "validate",
    is_globally_visible: true,
    active_version_id: "version-1",
    created_at: "2026-04-26T10:00:00Z",
    updated_at: "2026-04-26T10:00:00Z",
    ...overrides,
  };
}

function adminPluginEvent(overrides: Partial<AdminPluginEventRead> = {}): AdminPluginEventRead {
  return {
    name: "sync",
    mode: "short_lived",
    function_name: "sync_now",
    title: "Sync",
    description: "Sync event",
    config_schema_json: {},
    default_config_json: {},
    config_json: {},
    is_enabled: true,
    schedule_mode: "manual",
    schedule_interval_seconds: null,
    schedule_cron: null,
    ...overrides,
  };
}

function adminPluginDetail(
  overrides: Partial<AdminPluginDetailRead> = {},
): AdminPluginDetailRead {
  const base = adminPluginListItem();
  return {
    ...base,
    active_version: null,
    versions: [],
    events: [adminPluginEvent()],
    run_state: {
      id: "run-1",
      plugin_id: base.id,
      current_version_id: "version-1",
      process_type: "service",
      pid: 123,
      status: "running",
      heartbeat_at: "2026-04-26T10:00:00Z",
      error_text: null,
      meta_json: {},
      updated_at: "2026-04-26T10:00:00Z",
    },
    ...overrides,
  };
}

describe("AdminPluginsPage", () => {
  beforeEach(() => {
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    window.localStorage.clear();
  });

  it("shows an access card when the user lacks plugin permissions", () => {
    resetUserStore({});

    render(<AdminPluginsPage />);

    expect(screen.getByText("plugins:noPermission")).toBeInTheDocument();
    expect(mocks.listAdminPlugins).not.toHaveBeenCalled();
  });

  it("loads admin plugins and saves the current global config", async () => {
    resetUserStore({ "plugins:read": true, "plugins:write": true });
    mocks.listAdminPlugins.mockResolvedValue([adminPluginListItem()]);
    mocks.getAdminPlugin.mockResolvedValue(adminPluginDetail());
    mocks.listAdminPluginGroupVisibility.mockResolvedValue([]);
    mocks.listAdminPluginSharedPackages.mockResolvedValue([]);
    mocks.listGroups.mockResolvedValue({
      items: [
        {
          gid: "group-1",
          name: "Core Team",
          owner_uid: "u-1",
          parent_group_id: null,
          group_path: "/core",
          invite_quota_remaining: null,
          invite_quota_unlimited: true,
          description: null,
          created_at: "2026-04-26T10:00:00Z",
          updated_at: "2026-04-26T10:00:00Z",
        },
      ],
      page: 1,
      page_size: 200,
      total: 1,
      total_pages: 1,
    });
    mocks.updateAdminPluginConfig.mockResolvedValue(adminPluginDetail());

    render(<AdminPluginsPage />);

    expect(await screen.findByText("Ops Admin")).toBeInTheDocument();
    expect(await screen.findByText("plugins:globalConfigTitle")).toBeInTheDocument();
    expect(screen.queryByText("plugins:eventScheduleTitle")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "plugins:saveGlobalConfig" }));

    await waitFor(() => {
      expect(mocks.updateAdminPluginConfig).toHaveBeenCalledWith("admin-plugin-1", { retries: 3 });
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("plugins:saveGlobalConfigSuccess");
  });
});
