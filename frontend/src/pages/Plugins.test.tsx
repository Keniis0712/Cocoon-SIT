import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PluginsPage from "@/pages/Plugins";
import type { UserPluginRead } from "@/api/types/plugins";

const mocks = vi.hoisted(() => ({
  listChatGroups: vi.fn(),
  getCocoons: vi.fn(),
  listWorkspacePlugins: vi.fn(),
  listWorkspacePluginTargetBindings: vi.fn(),
  getChatGroupPluginConfig: vi.fn(),
  setWorkspacePluginEnabled: vi.fn(),
  updateWorkspacePluginEventSchedule: vi.fn(),
  clearWorkspacePluginError: vi.fn(),
  addWorkspacePluginTargetBinding: vi.fn(),
  deleteWorkspacePluginTargetBinding: vi.fn(),
  setChatGroupPluginEnabled: vi.fn(),
  updateWorkspacePluginConfig: vi.fn(),
  updateChatGroupPluginConfig: vi.fn(),
  validateWorkspacePluginConfig: vi.fn(),
  validateChatGroupPluginConfig: vi.fn(),
  clearChatGroupPluginError: vi.fn(),
  showErrorToast: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("@/api/chatGroups", () => ({
  listChatGroups: mocks.listChatGroups,
}));

vi.mock("@/api/cocoons", () => ({
  getCocoons: mocks.getCocoons,
}));

vi.mock("@/api/plugins", () => ({
  listWorkspacePlugins: mocks.listWorkspacePlugins,
  listWorkspacePluginTargetBindings: mocks.listWorkspacePluginTargetBindings,
  getChatGroupPluginConfig: mocks.getChatGroupPluginConfig,
  setWorkspacePluginEnabled: mocks.setWorkspacePluginEnabled,
  updateWorkspacePluginEventSchedule: mocks.updateWorkspacePluginEventSchedule,
  clearWorkspacePluginError: mocks.clearWorkspacePluginError,
  addWorkspacePluginTargetBinding: mocks.addWorkspacePluginTargetBinding,
  deleteWorkspacePluginTargetBinding: mocks.deleteWorkspacePluginTargetBinding,
  setChatGroupPluginEnabled: mocks.setChatGroupPluginEnabled,
  updateWorkspacePluginConfig: mocks.updateWorkspacePluginConfig,
  updateChatGroupPluginConfig: mocks.updateChatGroupPluginConfig,
  validateWorkspacePluginConfig: mocks.validateWorkspacePluginConfig,
  validateChatGroupPluginConfig: mocks.validateChatGroupPluginConfig,
  clearChatGroupPluginError: mocks.clearChatGroupPluginError,
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

function workspacePlugin(overrides: Partial<UserPluginRead> = {}): UserPluginRead {
  return {
    id: "plugin-1",
    name: "ops-helper",
    display_name: "Ops Helper",
    plugin_type: "external",
    status: "ready",
    is_globally_visible: true,
    is_visible: true,
    is_enabled: false,
    config_schema_json: {},
    default_config_json: {},
    user_config_schema_json: {},
    user_default_config_json: {},
    user_config_json: {},
    user_error_text: null,
    user_error_at: null,
    events: [],
    ...overrides,
  };
}

describe("PluginsPage", () => {
  beforeEach(() => {
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    mocks.listWorkspacePluginTargetBindings.mockResolvedValue([]);
    mocks.getChatGroupPluginConfig.mockResolvedValue(null);
    mocks.getCocoons.mockResolvedValue({ items: [], page: 1, page_size: 200, total: 0, total_pages: 0 });
    mocks.listChatGroups.mockResolvedValue([]);
  });

  it("loads workspace plugins and toggles the selected plugin state", async () => {
    mocks.listWorkspacePlugins.mockResolvedValue([workspacePlugin()]);
    mocks.setWorkspacePluginEnabled.mockResolvedValue(workspacePlugin({ is_enabled: true }));

    render(<PluginsPage />);

    expect((await screen.findAllByText("Ops Helper")).length).toBeGreaterThan(0);

    const [userSwitch] = await screen.findAllByRole("switch");
    fireEvent.click(userSwitch);

    await waitFor(() => {
      expect(mocks.setWorkspacePluginEnabled).toHaveBeenCalledWith("plugin-1", true);
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("plugins:toggleSuccess");
  });

  it("clears plugin errors through the user error action", async () => {
    mocks.listWorkspacePlugins.mockResolvedValue([
      workspacePlugin({
        is_enabled: true,
        user_error_text: "invalid token",
        user_error_at: "2026-04-26T10:00:00Z",
      }),
    ]);
    mocks.clearWorkspacePluginError.mockResolvedValue(
      workspacePlugin({
        is_enabled: true,
        user_error_text: null,
        user_error_at: null,
      }),
    );

    render(<PluginsPage />);

    expect(await screen.findByText("invalid token")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "plugins:clearUserError" }));

    await waitFor(() => {
      expect(mocks.clearWorkspacePluginError).toHaveBeenCalledWith("plugin-1");
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("plugins:clearErrorSuccess");
  });
});
