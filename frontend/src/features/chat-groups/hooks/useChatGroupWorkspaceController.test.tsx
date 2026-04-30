import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useChatGroupWorkspaceController } from "@/features/chat-groups/hooks/useChatGroupWorkspaceController";
import { useUserStore } from "@/store/useUserStore";

const mocks = vi.hoisted(() => ({
  listAdminUsers: vi.fn(),
  getCharacters: vi.fn(),
  getChatGroup: vi.fn(),
  getChatGroupState: vi.fn(),
  listChatGroupMembers: vi.fn(),
  listChatGroupMessages: vi.fn(),
  sendChatGroupMessage: vi.fn(),
  removeChatGroupMember: vi.fn(),
  addChatGroupMember: vi.fn(),
  updateChatGroupMember: vi.fn(),
  retractChatGroupMessage: vi.fn(),
  listModelProviders: vi.fn(),
  bindChatGroupTags: vi.fn(),
  listTags: vi.fn(),
  listChatGroupWakeups: vi.fn(),
  showErrorToast: vi.fn(),
  toastError: vi.fn(),
  toastSuccess: vi.fn(),
}));

vi.mock("@/api/admin-users", () => ({
  listAdminUsers: mocks.listAdminUsers,
}));

vi.mock("@/api/characters", () => ({
  getCharacters: mocks.getCharacters,
}));

vi.mock("@/api/chatGroups", () => ({
  addChatGroupMember: mocks.addChatGroupMember,
  getChatGroup: mocks.getChatGroup,
  getChatGroupState: mocks.getChatGroupState,
  listChatGroupMembers: mocks.listChatGroupMembers,
  listChatGroupMessages: mocks.listChatGroupMessages,
  removeChatGroupMember: mocks.removeChatGroupMember,
  retractChatGroupMessage: mocks.retractChatGroupMessage,
  sendChatGroupMessage: mocks.sendChatGroupMessage,
  updateChatGroupMember: mocks.updateChatGroupMember,
}));

vi.mock("@/api/providers", () => ({
  listModelProviders: mocks.listModelProviders,
}));

vi.mock("@/api/tags", () => ({
  bindChatGroupTags: mocks.bindChatGroupTags,
  listTags: mocks.listTags,
}));

vi.mock("@/api/wakeups", () => ({
  listChatGroupWakeups: mocks.listChatGroupWakeups,
}));

vi.mock("@/api/client", () => ({
  localizeApiMessage: (message: string) => message,
  showErrorToast: mocks.showErrorToast,
}));

vi.mock("@/components/composes/useConfirmDialog", () => ({
  useConfirmDialog: () => ({
    confirm: vi.fn().mockResolvedValue(true),
    confirmDialog: <div data-testid="confirm-dialog" />,
  }),
}));

vi.mock("@/hooks/useChatGroupWs", () => ({
  useChatGroupWs: vi.fn(),
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
      can_manage_system: true,
      can_manage_users: true,
      can_manage_prompts: true,
      can_manage_providers: true,
      timezone: "Asia/Shanghai",
      permissions: { "users:read": true },
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

describe("useChatGroupWorkspaceController", () => {
  beforeEach(() => {
    for (const mock of Object.values(mocks)) {
      mock.mockReset();
    }
    seedUserStore();
    mocks.getChatGroup.mockResolvedValue({
      id: "room-1",
      name: "Ops Room",
      owner_user_id: "u-1",
      character_id: "char-1",
      selected_model_id: "model-1",
      default_temperature: 0.7,
      max_context_messages: 24,
      auto_compaction_enabled: true,
      external_platform: null,
      external_group_id: null,
      external_account_id: null,
      created_at: "2026-04-26T10:00:00Z",
    });
    mocks.getChatGroupState.mockResolvedValue({
      relation_score: 50,
      persona_json: {},
      active_tags_json: [],
      current_wakeup_task_id: null,
    });
    mocks.listChatGroupMembers.mockResolvedValue([
      {
        id: "member-1",
        room_id: "room-1",
        user_id: "u-1",
        member_role: "admin",
        created_at: "2026-04-26T10:00:00Z",
      },
    ]);
    mocks.listChatGroupMessages.mockResolvedValue({
      items: [],
      has_more: false,
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
          available_models: [
            { id: 1, model_name: "gpt-test" },
          ],
        },
      ],
    });
    mocks.listChatGroupWakeups.mockResolvedValue([]);
    mocks.listTags.mockResolvedValue([]);
    mocks.listAdminUsers.mockResolvedValue({ items: [] });
    mocks.sendChatGroupMessage.mockResolvedValue({
      accepted: true,
      dispatch_status: "queued",
      debounce_until: "2026-04-26T12:00:10Z",
      user_message: {
        id: 20,
        message_uid: "pending-20",
        cocoon_id: null,
        chat_group_id: 1,
        source_cocoon_id: null,
        origin_cocoon_id: null,
        sender_user_id: null,
        role: "user",
        content: "hello group",
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

  it("loads workspace state and sends optimistic group messages with sender context", async () => {
    const { result } = renderHook(() => useChatGroupWorkspaceController("room-1"));

    await waitFor(() => {
      expect(result.current.room?.name).toBe("Ops Room");
    });

    act(() => {
      result.current.onMessageInputChange("hello group");
    });

    await act(async () => {
      await result.current.handleSendMessage();
    });

    expect(mocks.sendChatGroupMessage).toHaveBeenCalledWith(
      "room-1",
      expect.objectContaining({
        content: "hello group",
        timezone: "Asia/Shanghai",
      }),
    );
    expect(result.current.visibleMessages.at(-1)).toMatchObject({
      content: "hello group",
      sender_user_id: "u-1",
    });
    expect(result.current.session?.dispatchState).toBe("queued");
    expect(result.current.canManage).toBe(true);
  });
});
