import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CocoonsPage from "@/pages/Cocoons";
import { useUserStore } from "@/store/useUserStore";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  getCharacters: vi.fn(),
  listModelProviders: vi.fn(),
  getSystemSettings: vi.fn(),
  getCocoonTree: vi.fn(),
  getCocoon: vi.fn(),
  createCocoon: vi.fn(),
  updateCocoon: vi.fn(),
  deleteCocoon: vi.fn(),
  confirm: vi.fn(),
  showErrorToast: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock("@/api/characters", () => ({
  getCharacters: mocks.getCharacters,
}));

vi.mock("@/api/providers", () => ({
  listModelProviders: mocks.listModelProviders,
}));

vi.mock("@/api/settings", () => ({
  getSystemSettings: mocks.getSystemSettings,
}));

vi.mock("@/api/cocoons", () => ({
  getCocoonTree: mocks.getCocoonTree,
  getCocoon: mocks.getCocoon,
  createCocoon: mocks.createCocoon,
  updateCocoon: mocks.updateCocoon,
  deleteCocoon: mocks.deleteCocoon,
}));

vi.mock("@/api/client", () => ({
  getErrorMessage: (error: unknown) => (error instanceof Error ? error.message : String(error)),
  localizeApiMessage: (message: string) => message,
  showErrorToast: mocks.showErrorToast,
}));

vi.mock("@/components/composes/useConfirmDialog", () => ({
  useConfirmDialog: () => ({
    confirm: mocks.confirm,
    confirmDialog: <div data-testid="confirm-dialog" />,
  }),
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

function treeNode(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    name: "Root Cocoon",
    owner_uid: null,
    kind: "private",
    chat_group_id: null,
    parent_id: null,
    last_read_msg_id: null,
    debounce_until: null,
    dispatch_status: "idle",
    sync_mode: "manual",
    fork_anchor_msg_id: null,
    fork_at_msg_id: null,
    fork_at_ts: null,
    active_checkpoint_id: null,
    rollback_activated_at: null,
    context_prompt: null,
    max_context_tokens: null,
    max_rounds: null,
    compact_memory_max_items: 10,
    auto_compaction_trigger_rounds: 5,
    auto_compaction_message_count: 24,
    auto_compaction_memory_max_items: 10,
    manual_compaction_message_count: 24,
    manual_compaction_memory_max_items: 10,
    manual_compaction_mode: "default",
    character_id: 1,
    provider_id: 10,
    selected_model_id: 101,
    created_at: "2026-04-26T10:00:00Z",
    has_children: false,
    children: [],
    ...overrides,
  };
}

function cocoon(overrides: Record<string, unknown> = {}) {
  return {
    id: 1,
    name: "Root Cocoon",
    owner_uid: null,
    default_temperature: null,
    max_context_messages: 24,
    auto_compaction_enabled: true,
    kind: "private",
    chat_group_id: null,
    parent_id: null,
    last_read_msg_id: null,
    debounce_until: null,
    dispatch_status: "idle",
    sync_mode: "manual",
    fork_anchor_msg_id: null,
    fork_at_msg_id: null,
    fork_at_ts: null,
    active_checkpoint_id: null,
    rollback_activated_at: null,
    context_prompt: null,
    max_context_tokens: null,
    max_rounds: null,
    compact_memory_max_items: 10,
    auto_compaction_trigger_rounds: 5,
    auto_compaction_message_count: 24,
    auto_compaction_memory_max_items: 10,
    manual_compaction_message_count: 24,
    manual_compaction_memory_max_items: 10,
    manual_compaction_mode: "default",
    character_id: 1,
    provider_id: 10,
    selected_model_id: 101,
    created_at: "2026-04-26T10:00:00Z",
    character: { name: "Analyst" },
    selected_model: { model_name: "gpt-test" },
    ...overrides,
  };
}

function seedPage() {
  useUserStore.setState({
    userInfo: null,
    isLoggedIn: false,
    login: useUserStore.getState().login,
    logout: useUserStore.getState().logout,
    updateInfo: useUserStore.getState().updateInfo,
    getToken: useUserStore.getState().getToken,
  });
  mocks.getCharacters.mockResolvedValue({
    items: [
      {
        id: 1,
        name: "Analyst",
        owner_uid: null,
        visibility: "private",
        description: "Character",
        personality_prompt: "Prompt",
        created_at: "2026-04-26T10:00:00Z",
      },
    ],
  });
  mocks.listModelProviders.mockResolvedValue({
    items: [
      {
        id: 10,
        name: "OpenAI",
        base_url: "https://example.com",
        is_enabled: true,
        created_at: "2026-04-26T10:00:00Z",
        updated_at: "2026-04-26T10:00:00Z",
        available_models: [
          {
            id: 101,
            provider_id: 10,
            model_name: "gpt-test",
            created_at: "2026-04-26T10:00:00Z",
            updated_at: "2026-04-26T10:00:00Z",
          },
        ],
      },
    ],
  });
  mocks.getCocoonTree.mockResolvedValue({
    items: [treeNode()],
    page: 1,
    page_size: 20,
    total: 1,
    total_pages: 1,
    parent_id: null,
    max_depth: 2,
  });
  mocks.getCocoon.mockResolvedValue(cocoon());
  mocks.confirm.mockResolvedValue(true);
}

describe("CocoonsPage", () => {
  beforeEach(() => {
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    seedPage();
  });

  it("loads the tree and navigates into the selected workspace", async () => {
    render(<CocoonsPage />);

    expect((await screen.findAllByText("Root Cocoon")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "cocoons.enterWorkspace" }));

    expect(mocks.navigate).toHaveBeenCalledWith("/cocoons/1");
  });

  it("creates a new root cocoon from the dialog", async () => {
    mocks.createCocoon.mockResolvedValue(cocoon({ id: 2, name: "Branch Cocoon" }));

    render(<CocoonsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "cocoons.newRoot" }));
    const dialog = await screen.findByRole("dialog");
    const textboxes = within(dialog).getAllByRole("textbox");

    fireEvent.change(textboxes[0], {
      target: { value: "Branch Cocoon" },
    });
    fireEvent.change(within(dialog).getByLabelText("cocoons.selectRole"), {
      target: { value: "1" },
    });
    fireEvent.change(within(dialog).getByLabelText("cocoons.selectModel"), {
      target: { value: "101" },
    });
    fireEvent.change(textboxes[1], {
      target: { value: "40" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "cocoons.dialogCreateRoot" }));

    await waitFor(() => {
      expect(mocks.createCocoon).toHaveBeenCalledWith({
        name: "Branch Cocoon",
        character_id: 1,
        selected_model_id: 101,
        max_context_messages: 40,
        auto_compaction_enabled: true,
      });
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("cocoons.rootCreated");
  });

  it("creates a child cocoon with inherited role and model when left on inherit", async () => {
    mocks.createCocoon.mockResolvedValue(cocoon({ id: 3, name: "Root Cocoon / child", parent_id: 1 }));
    mocks.getCocoonTree.mockImplementation((_page: number, _pageSize: number, _maxDepth: number, parentId?: number | null) =>
      Promise.resolve({
        items: parentId ? [] : [treeNode()],
        page: 1,
        page_size: 20,
        total: parentId ? 0 : 1,
        total_pages: 1,
        parent_id: parentId ?? null,
        max_depth: 2,
      }),
    );

    render(<CocoonsPage />);

    await screen.findAllByText("Root Cocoon");
    fireEvent.click(screen.getByRole("button", { name: "cocoons.newChild" }));

    const dialog = await screen.findByRole("dialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "cocoons.dialogCreateChild" }));

    await waitFor(() => {
      expect(mocks.createCocoon).toHaveBeenCalledWith({
        name: "Root Cocoon / child",
        parent_id: 1,
        max_context_messages: undefined,
        auto_compaction_enabled: true,
      });
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("cocoons.childCreated");
  });

  it("deletes the selected cocoon after confirmation", async () => {
    mocks.deleteCocoon.mockResolvedValue(cocoon());

    render(<CocoonsPage />);

    expect((await screen.findAllByText("Root Cocoon")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "common.delete" }));

    await waitFor(() => {
      expect(mocks.confirm).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(mocks.deleteCocoon).toHaveBeenCalledWith(1);
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("cocoons.deleted");
  });
});
