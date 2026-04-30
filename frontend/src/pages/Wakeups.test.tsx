import { Children, isValidElement } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const routeState = vi.hoisted(() => ({
  searchParams: new URLSearchParams(),
}));

const mocks = vi.hoisted(() => ({
  listAuditWakeups: vi.fn(),
  resolveActualId: vi.fn(),
  showErrorToast: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useSearchParams: () => [routeState.searchParams],
}));

vi.mock("@/api/wakeups", () => ({
  listAuditWakeups: mocks.listAuditWakeups,
}));

vi.mock("@/api/id-map", () => ({
  resolveActualId: mocks.resolveActualId,
}));

vi.mock("@/api/client", () => ({
  showErrorToast: mocks.showErrorToast,
}));

vi.mock("@/features/workspace/utils", () => ({
  formatWorkspaceTime: (value: string) => `fmt:${value}`,
}));

vi.mock("@/components/AccessCard", () => ({
  default: ({ description }: { description: string }) => <div>{description}</div>,
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

vi.mock("@/components/ui/label", () => ({
  Label: ({ children }: { children: React.ReactNode }) => <label>{children}</label>,
}));

vi.mock("@/components/ui/checkbox", () => ({
  Checkbox: ({
    checked,
    onCheckedChange,
  }: {
    checked: boolean;
    onCheckedChange?: (checked: boolean) => void;
  }) => (
    <input
      aria-label="only-ai"
      checked={checked}
      type="checkbox"
      onChange={(event) => onCheckedChange?.(event.target.checked)}
    />
  ),
}));

vi.mock("@/components/ui/select", () => ({
  Select: ({
    value,
    onValueChange,
    children,
  }: {
    value: string;
    onValueChange: (value: string) => void;
    children: React.ReactNode;
  }) => {
    const options: React.ReactElement[] = [];
    const collect = (node: React.ReactNode) => {
      for (const child of Children.toArray(node)) {
        if (typeof child === "string" || typeof child === "number") {
          continue;
        }
        if (!isValidElement(child)) {
          continue;
        }
        if (child.type === "option") {
          options.push(child);
        } else {
          collect((child as React.ReactElement<{ children?: React.ReactNode }>).props.children);
        }
      }
    };
    collect(children);
    return (
      <select value={value} onChange={(event) => onValueChange(event.target.value)}>
        {options}
      </select>
    );
  },
  SelectTrigger: ({ children }: { children?: React.ReactNode }) => <>{children}</>,
  SelectValue: () => null,
  SelectContent: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  SelectItem: ({
    value,
    children,
  }: {
    value: string;
    children: React.ReactNode;
  }) => <option value={value}>{children}</option>,
}));

import WakeupsPage from "@/pages/Wakeups";
import { useUserStore } from "@/store/useUserStore";

function seedUserStore(canAudit: boolean) {
  useUserStore.setState({
    userInfo: canAudit
      ? {
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
        }
      : {
          access_token: "token",
          refresh_token: "refresh-token",
          token_type: "bearer",
          expires_in_seconds: 3600,
          uid: "u-1",
          username: "alice",
          parent_uid: null,
          user_path: null,
          role: "member",
          role_level: 0,
          can_audit: false,
          can_manage_system: false,
          can_manage_users: false,
          can_manage_prompts: false,
          can_manage_providers: false,
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

describe("WakeupsPage", () => {
  beforeEach(() => {
    seedUserStore(true);
    routeState.searchParams = new URLSearchParams("status=queued&targetType=cocoon&targetId=12");
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    mocks.resolveActualId.mockImplementation((_kind: string, id: number) => `actual-${id}`);
    mocks.listAuditWakeups.mockResolvedValue([
      {
        id: "w-1",
        target_type: "cocoon",
        target_id: "actual-12",
        target_name: "Root Cocoon",
        status: "queued",
        reason: "idle reminder",
        scheduled_by: "scheduler",
        trigger_kind: "idle",
        is_ai_wakeup: true,
        run_at: "2026-04-26T10:00:00Z",
        created_at: "2026-04-26T09:00:00Z",
        cancelled_reason: null,
      },
      {
        id: "w-2",
        target_type: "chat_group",
        target_id: "room-1",
        target_name: "Ops Room",
        status: "cancelled",
        reason: "",
        scheduled_by: null,
        trigger_kind: null,
        is_ai_wakeup: false,
        run_at: "2026-04-26T11:00:00Z",
        created_at: "2026-04-26T09:30:00Z",
        cancelled_reason: "duplicate",
      },
    ]);
  });

  it("loads wakeups with scoped audit filters and renders the returned tasks", async () => {
    render(<WakeupsPage />);

    await waitFor(() => {
      expect(mocks.listAuditWakeups).toHaveBeenCalledWith({
        status: "queued",
        target_type: "cocoon",
        target_id: "actual-12",
        only_ai: true,
        limit: 200,
      });
    });

    expect(await screen.findByText("Root Cocoon")).toBeInTheDocument();
    expect(screen.getByText("Ops Room")).toBeInTheDocument();
    expect(screen.getByText("idle reminder")).toBeInTheDocument();
    expect(screen.getByText("wakeups:cancelledReason")).toBeInTheDocument();
  });

  it("allows audit users to broaden results by disabling the ai-only filter", async () => {
    render(<WakeupsPage />);

    await screen.findByText("Root Cocoon");
    fireEvent.click(screen.getByRole("checkbox", { name: "only-ai" }));

    await waitFor(() => {
      expect(mocks.listAuditWakeups).toHaveBeenLastCalledWith({
        status: "queued",
        target_type: "cocoon",
        target_id: "actual-12",
        only_ai: false,
        limit: 200,
      });
    });
  });

  it("shows the access guard when the current user cannot audit wakeups", () => {
    seedUserStore(false);

    render(<WakeupsPage />);

    expect(screen.getByText("wakeups:noPermission")).toBeInTheDocument();
    expect(mocks.listAuditWakeups).not.toHaveBeenCalled();
  });
});
