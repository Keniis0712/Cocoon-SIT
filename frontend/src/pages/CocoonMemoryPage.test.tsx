import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const routeState = vi.hoisted(() => ({
  cocoonId: "1",
}));

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  getCocoon: vi.fn(),
  getCocoonMemories: vi.fn(),
  deleteCocoonMemory: vi.fn(),
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
  deleteCocoonMemory: mocks.deleteCocoonMemory,
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
    mocks.getCocoonMemories.mockResolvedValue({
      items: [
        {
          id: 101,
          cocoon_id: 1,
          origin_cocoon_id: null,
          source_message_id: null,
          chroma_document_id: "mem-101",
          role_key: "memory",
          source_kind: "summary",
          content: "Conversation summary",
          visibility: 0,
          importance: 3,
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
    expect(screen.getByText("focus")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "backToChat" }));
    expect(mocks.navigate).toHaveBeenCalledWith("/cocoons/1");
  });

  it("deletes a memory chunk after confirmation and updates the rendered list", async () => {
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
});
