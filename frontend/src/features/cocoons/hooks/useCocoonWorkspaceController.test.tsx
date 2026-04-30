import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useCocoonWorkspaceController } from "@/features/cocoons/hooks/useCocoonWorkspaceController";
import { useUserStore } from "@/store/useUserStore";

const mocks = vi.hoisted(() => ({
  getCocoon: vi.fn(),
  getCocoonSessionState: vi.fn(),
  getCocoonMessages: vi.fn(),
  sendCocoonMessage: vi.fn(),
  updateCocoon: vi.fn(),
  compactCocoonContext: vi.fn(),
  retryCocoonReply: vi.fn(),
  listModelProviders: vi.fn(),
  getSystemSettings: vi.fn(),
  bindCocoonTags: vi.fn(),
  listTags: vi.fn(),
  listCocoonWakeups: vi.fn(),
  showErrorToast: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/api/cocoons", () => ({
  compactCocoonContext: mocks.compactCocoonContext,
  getCocoon: mocks.getCocoon,
  getCocoonMessages: mocks.getCocoonMessages,
  getCocoonSessionState: mocks.getCocoonSessionState,
  retryCocoonReply: mocks.retryCocoonReply,
  sendCocoonMessage: mocks.sendCocoonMessage,
  updateCocoon: mocks.updateCocoon,
}));

vi.mock("@/api/providers", () => ({
  listModelProviders: mocks.listModelProviders,
}));

vi.mock("@/api/settings", () => ({
  getSystemSettings: mocks.getSystemSettings,
}));

vi.mock("@/api/tags", () => ({
  bindCocoonTags: mocks.bindCocoonTags,
  listTags: mocks.listTags,
}));

vi.mock("@/api/wakeups", () => ({
  listCocoonWakeups: mocks.listCocoonWakeups,
}));

vi.mock("@/api/client", () => ({
  localizeApiMessage: (message: string) => message,
  showErrorToast: mocks.showErrorToast,
}));

vi.mock("@/hooks/useCocoonWs", () => ({
  useCocoonWs: vi.fn(),
}));

vi.mock("react-router-dom", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("sonner", () => ({
  toast: {
    error: mocks.toastError,
    success: mocks.toastSuccess,
  },
}));

function seedUserStore() {
  useUserStore.setState({
    userInfo: {
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
      can_manage_system: false,
      can_manage_users: true,
      can_manage_prompts: true,
      can_manage_providers: true,
      timezone: "Asia/Shanghai",
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

describe("useCocoonWorkspaceController", () => {
  beforeEach(() => {
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    seedUserStore();
    mocks.getCocoon.mockResolvedValue({
      id: 1,
      name: "Root Cocoon",
      provider_id: 10,
      selected_model_id: 101,
      dispatch_status: "idle",
      tags: [],
      dispatch_job: null,
    });
    mocks.getCocoonSessionState.mockResolvedValue({
      relation_score: 50,
      persona_json: {},
      active_tags: [],
      current_model_id: 101,
      current_wakeup_task_id: null,
      dispatch_status: "idle",
      debounce_until: null,
    });
    mocks.getCocoonMessages.mockResolvedValue({
      items: [],
      has_more: false,
    });
    mocks.listModelProviders.mockResolvedValue({
      items: [
        {
          id: 10,
          available_models: [
            { id: 101, model_name: "gpt-test" },
          ],
        },
      ],
    });
    mocks.listTags.mockResolvedValue([]);
    mocks.listCocoonWakeups.mockResolvedValue([]);
    mocks.sendCocoonMessage.mockResolvedValue({
      accepted: true,
      dispatch_status: "queued",
      debounce_until: "2026-04-26T12:00:10Z",
      user_message: {
        id: 10,
        message_uid: "pending-10",
        cocoon_id: 1,
        chat_group_id: null,
        source_cocoon_id: null,
        origin_cocoon_id: null,
        sender_user_id: null,
        role: "user",
        content: "hello from hook",
        is_thought: false,
        visibility_level: 0,
        delivery_status: "pending",
        processing_status: "queued",
        reply_to_message_id: null,
        created_at: "2026-04-26T12:00:00Z",
        updated_at: null,
      },
    });
  });

  it("loads workspace data and delegates optimistic send through the shared controller", async () => {
    const { result } = renderHook(() => useCocoonWorkspaceController(1));

    await waitFor(() => {
      expect(result.current.selectedCocoon?.name).toBe("Root Cocoon");
    });

    act(() => {
      result.current.onMessageInputChange("hello from hook");
    });

    await act(async () => {
      await result.current.handleSendMessage();
    });

    expect(mocks.sendCocoonMessage).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        content: "hello from hook",
        timezone: "Asia/Shanghai",
      }),
    );
    expect(result.current.visibleMessages.at(-1)?.content).toBe("hello from hook");
    expect(result.current.session?.dispatchState).toBe("queued");
  });
});
