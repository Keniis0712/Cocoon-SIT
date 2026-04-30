import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ChatGroupsPage from "@/pages/ChatGroupsPage";

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  listChatGroups: vi.fn(),
  createChatGroup: vi.fn(),
  updateChatGroup: vi.fn(),
  deleteChatGroup: vi.fn(),
  getCharacters: vi.fn(),
  listModelProviders: vi.fn(),
  confirm: vi.fn(),
  showErrorToast: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock("@/api/chatGroups", () => ({
  listChatGroups: mocks.listChatGroups,
  createChatGroup: mocks.createChatGroup,
  updateChatGroup: mocks.updateChatGroup,
  deleteChatGroup: mocks.deleteChatGroup,
}));

vi.mock("@/api/characters", () => ({
  getCharacters: mocks.getCharacters,
}));

vi.mock("@/api/providers", () => ({
  listModelProviders: mocks.listModelProviders,
}));

vi.mock("@/api/client", () => ({
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

function room(overrides: Record<string, unknown> = {}) {
  return {
    id: "room-1",
    name: "Ops Room",
    owner_user_id: "1",
    character_id: "1",
    selected_model_id: "101",
    default_temperature: 0.7,
    max_context_messages: 24,
    auto_compaction_enabled: true,
    external_platform: null,
    external_group_id: null,
    external_account_id: null,
    created_at: "2026-04-26T10:00:00Z",
    ...overrides,
  };
}

function seedPage() {
  mocks.listChatGroups.mockResolvedValue([room()]);
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
}

describe("ChatGroupsPage", () => {
  beforeEach(() => {
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    seedPage();
    mocks.confirm.mockResolvedValue(true);
  });

  it("loads rooms and navigates into the selected workspace", async () => {
    render(<ChatGroupsPage />);

    expect((await screen.findAllByText("Ops Room")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "chatGroups:openWorkspace" }));

    expect(mocks.navigate).toHaveBeenCalledWith("/chat-groups/room-1");
  });

  it("creates a new room from the dialog form", async () => {
    mocks.createChatGroup.mockResolvedValue(room({ id: "room-2", name: "Research Room" }));

    render(<ChatGroupsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "chatGroups:newRoom" }));
    const dialog = await screen.findByRole("dialog");
    const textboxes = within(dialog).getAllByRole("textbox");

    fireEvent.change(textboxes[0], {
      target: { value: "Research Room" },
    });
    fireEvent.change(within(dialog).getByLabelText("chatGroups:selectCharacter"), {
      target: { value: "1" },
    });
    fireEvent.change(within(dialog).getByLabelText("common:selectModel"), {
      target: { value: "101" },
    });
    fireEvent.change(textboxes[1], {
      target: { value: "0.9" },
    });
    fireEvent.change(textboxes[2], {
      target: { value: "32" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: "chatGroups:newRoom" }));

    await waitFor(() => {
      expect(mocks.createChatGroup).toHaveBeenCalledWith({
        name: "Research Room",
        character_id: 1,
        selected_model_id: 101,
        default_temperature: 0.9,
        max_context_messages: 32,
        auto_compaction_enabled: true,
      });
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("chatGroups:created");
  });

  it("deletes the selected room after confirmation", async () => {
    mocks.deleteChatGroup.mockResolvedValue(room());

    render(<ChatGroupsPage />);

    expect((await screen.findAllByText("Ops Room")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "chatGroups:deleteRoom" }));

    await waitFor(() => {
      expect(mocks.confirm).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(mocks.deleteChatGroup).toHaveBeenCalledWith("room-1");
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("chatGroups:deleted");
  });
});
