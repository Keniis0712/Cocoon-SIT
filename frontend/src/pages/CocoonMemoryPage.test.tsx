import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const routeState = vi.hoisted(() => ({
  cocoonId: "1",
}));

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  getCocoon: vi.fn(),
  getCocoonMemories: vi.fn(),
  updateCocoonMemory: vi.fn(),
  reorganizeCocoonMemories: vi.fn(),
  deleteCocoonMemory: vi.fn(),
  listTags: vi.fn(),
  confirm: vi.fn(),
  showErrorToast: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => mocks.navigate,
  useParams: () => ({ cocoonId: routeState.cocoonId }),
}));

vi.mock("@/api/cocoons", () => ({
  getCocoon: mocks.getCocoon,
  getCocoonMemories: mocks.getCocoonMemories,
  updateCocoonMemory: mocks.updateCocoonMemory,
  reorganizeCocoonMemories: mocks.reorganizeCocoonMemories,
  deleteCocoonMemory: mocks.deleteCocoonMemory,
}));

vi.mock("@/api/tags", () => ({
  listTags: mocks.listTags,
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
    description?: string;
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

vi.mock("@/components/ui/button", () => ({
  Button: ({
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

vi.mock("@/components/ui/badge", () => ({
  Badge: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

vi.mock("@/components/ui/card", () => ({
  Card: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardTitle: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardDescription: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  CardContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

import CocoonMemoryPage from "@/pages/CocoonMemoryPage";

describe("CocoonMemoryPage", () => {
  beforeEach(() => {
    routeState.cocoonId = "1";
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    mocks.confirm.mockResolvedValue(true);
    mocks.getCocoon.mockResolvedValue({
      id: 1,
      name: "Root Cocoon",
    });
    mocks.listTags.mockResolvedValue([
      {
        id: 1,
        actual_id: "tag-default-id",
        tag_id: "default",
        name: "default",
        brief: "Default memory boundary",
        visibility_mode: "private",
        is_system: true,
        visible_chat_group_ids: [],
        created_at: "2026-04-26T10:00:00Z",
        updated_at: "2026-04-26T10:00:00Z",
      },
      {
        id: 2,
        actual_id: "tag-focus-id",
        tag_id: "focus",
        name: "focus",
        brief: "Focus mode",
        visibility_mode: "private",
        is_system: false,
        visible_chat_group_ids: [],
        created_at: "2026-04-26T10:00:00Z",
        updated_at: "2026-04-26T10:00:00Z",
      },
    ]);
    mocks.getCocoonMemories.mockResolvedValue({
      overview: {
        total: 1,
        by_pool: { tree_private: 1 },
        by_type: { summary: 1 },
        by_status: { active: 1 },
        tag_cloud: [{ tag: "focus", count: 1 }],
        word_cloud: [{ word: "summary", count: 1 }],
        importance_average: 3,
        confidence_average: 3,
      },
      items: [
        {
          id: 101,
          cocoon_id: 1,
          memory_pool: "tree_private",
          memory_type: "summary",
          status: "active",
          origin_cocoon_id: null,
          source_message_id: null,
          chroma_document_id: "mem-101",
          role_key: "memory",
          source_kind: "runtime_analysis",
          content: "Conversation summary",
          visibility: 0,
          importance: 3,
          confidence: 3,
          access_count: 0,
          valid_until: null,
          last_accessed_at: null,
          timestamp: 1,
          is_thought: false,
          is_summary: true,
          created_at: "2026-04-26T10:00:00Z",
          source_message: null,
          tags: ["focus"],
        },
      ],
      page: 1,
      page_size: 100,
      total: 1,
      total_pages: 1,
    });
    mocks.deleteCocoonMemory.mockResolvedValue({});
    mocks.updateCocoonMemory.mockResolvedValue({});
    mocks.reorganizeCocoonMemories.mockResolvedValue({ status: "queued" });
  });

  it("redirects invalid cocoon ids back to the cocoon list", async () => {
    routeState.cocoonId = "oops";

    render(<CocoonMemoryPage />);

    await waitFor(() => {
      expect(mocks.navigate).toHaveBeenCalledWith("/cocoons", { replace: true });
    });
    expect(mocks.getCocoon).not.toHaveBeenCalled();
  });

  it("loads memory chunks and navigates back to the workspace", async () => {
    render(<CocoonMemoryPage />);

    expect(await screen.findByText("Conversation summary")).toBeInTheDocument();
    expect(screen.getAllByText("focus").length).toBeGreaterThan(0);
    expect(screen.queryByText("tree_private")).not.toBeInTheDocument();
    expect(screen.queryByText("runtime_analysis")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "backToChat" }));
    expect(mocks.navigate).toHaveBeenCalledWith("/cocoons/1");
  });

  it("deletes a memory chunk after confirmation and updates the rendered list", async () => {
    mocks.getCocoonMemories
      .mockResolvedValueOnce({
        overview: {
          total: 1,
          by_pool: { tree_private: 1 },
          by_type: { summary: 1 },
          by_status: { active: 1 },
          tag_cloud: [{ tag: "focus", count: 1 }],
          word_cloud: [{ word: "summary", count: 1 }],
          importance_average: 3,
          confidence_average: 3,
        },
        items: [
          {
            id: 101,
            cocoon_id: 1,
            memory_pool: "tree_private",
            memory_type: "summary",
            status: "active",
            origin_cocoon_id: null,
            source_message_id: null,
            chroma_document_id: "mem-101",
            role_key: "memory",
            source_kind: "runtime_analysis",
            content: "Conversation summary",
            visibility: 0,
            importance: 3,
            confidence: 3,
            access_count: 0,
            valid_until: null,
            last_accessed_at: null,
            timestamp: 1,
            is_thought: false,
            is_summary: true,
            created_at: "2026-04-26T10:00:00Z",
            source_message: null,
            tags: ["focus"],
          },
        ],
      })
      .mockResolvedValueOnce({
        overview: {
          total: 0,
          by_pool: {},
          by_type: {},
          by_status: {},
          tag_cloud: [],
          word_cloud: [],
          importance_average: 0,
          confidence_average: 0,
        },
        items: [],
      });

    render(<CocoonMemoryPage />);

    expect(await screen.findByText("Conversation summary")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "deleteMemory" }));

    await waitFor(() => {
      expect(mocks.confirm).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(mocks.deleteCocoonMemory).toHaveBeenCalledWith(1, 101);
    });
    await waitFor(() => {
      expect(screen.queryByText("Conversation summary")).not.toBeInTheDocument();
    });
    expect(mocks.toastSuccess).toHaveBeenCalledWith("memoryDeleted");
  });

  it("opens a dedicated tag popup and shows the default tag", async () => {
    render(<CocoonMemoryPage />);

    expect(await screen.findByText("Conversation summary")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "common.edit" }));
    fireEvent.click(screen.getByRole("button", { name: "memoryManageTags" }));

    expect(await screen.findAllByText("default")).not.toHaveLength(0);
    expect(screen.getByText("Default memory boundary")).toBeInTheDocument();
  });
});
