import { useEffect, useMemo, useState, type Dispatch, type ReactNode, type SetStateAction } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { listAdminUsers } from "@/api/admin-users";
import { getCharacters } from "@/api/characters";
import {
  addChatGroupMember,
  getChatGroup,
  getChatGroupState,
  listChatGroupMembers,
  listChatGroupMessages,
  removeChatGroupMember,
  retractChatGroupMessage,
  sendChatGroupMessage,
  updateChatGroupMember,
} from "@/api/chatGroups";
import { localizeApiMessage, showErrorToast } from "@/api/client";
import { resolveActualId } from "@/api/id-map";
import { listModelProviders } from "@/api/providers";
import { bindChatGroupTags, listTags } from "@/api/tags";
import type { AdminUserRead } from "@/api/types/access";
import type { CharacterRead, TagRead } from "@/api/types/catalog";
import type { MessageRead } from "@/api/types/chat";
import type { ChatGroupMemberRead, ChatGroupRead } from "@/api/types/chat-groups";
import type { ModelProviderRead } from "@/api/types/providers";
import type { WakeupTaskRead } from "@/api/types/wakeups";
import { listChatGroupWakeups } from "@/api/wakeups";
import { useConfirmDialog } from "@/components/composes/useConfirmDialog";
import { createRuntimeWsEventHandler } from "@/features/workspace/runtimeWsEvents";
import { useWorkspaceMessagingController } from "@/features/workspace/useWorkspaceMessagingController";
import { useChatGroupWs } from "@/hooks/useChatGroupWs";
import { useUserStore } from "@/store/useUserStore";

type MemberDialogState = {
  open: boolean;
  userId: string;
  role: "member" | "admin";
};

type ChatGroupWorkspaceController = {
  room: ChatGroupRead | null;
  characters: CharacterRead[];
  providers: ModelProviderRead[];
  availableTags: TagRead[];
  selectedTagIds: number[];
  isUpdatingTags: boolean;
  addTagValue: string;
  members: ChatGroupMemberRead[];
  userDirectory: AdminUserRead[];
  messageInput: string;
  currentAiWakeup: WakeupTaskRead | null;
  isLoading: boolean;
  isLoadingMore: boolean;
  isSending: boolean;
  hasMore: boolean;
  memberDialog: MemberDialogState;
  confirmDialog: ReactNode;
  session: ReturnType<typeof useWorkspaceMessagingController>["session"];
  viewportRef: ReturnType<typeof useWorkspaceMessagingController>["viewportRef"];
  visibleMessages: MessageRead[];
  currentUserId: string | null;
  currentMembership: ChatGroupMemberRead | null;
  canManage: boolean;
  characterName: string;
  modelLabel: string;
  availableAddableTags: TagRead[];
  userChoices: AdminUserRead[];
  memberNameMap: Map<string, string>;
  onMessageInputChange: (value: string) => void;
  handleSendMessage: () => Promise<void>;
  loadWorkspace: (initial?: boolean) => Promise<void>;
  loadOlderMessages: () => Promise<void>;
  handleRetractMessage: (message: MessageRead) => Promise<void>;
  handleAddMember: () => Promise<void>;
  handleChangeMemberRole: (member: ChatGroupMemberRead, nextRole: "member" | "admin") => Promise<void>;
  handleRemoveMember: (member: ChatGroupMemberRead) => Promise<void>;
  persistTagIds: (nextTagIds: number[]) => Promise<void>;
  handleAddTag: (value: string) => Promise<void>;
  canRetractMessage: (message: MessageRead) => boolean;
  displaySenderName: (message: MessageRead) => string;
  setMemberDialog: Dispatch<SetStateAction<MemberDialogState>>;
};

function resolveModelLabel(room: ChatGroupRead | null, providers: ModelProviderRead[]) {
  if (!room) {
    return "Unknown model";
  }
  for (const provider of providers) {
    for (const model of provider.available_models) {
      if (resolveActualId("model", model.id) === room.selected_model_id) {
        return `${provider.name} / ${model.model_name}`;
      }
    }
  }
  return "Unknown model";
}

export function useChatGroupWorkspaceController(roomId: string): ChatGroupWorkspaceController {
  const { t } = useTranslation("chatGroups");
  const navigate = useNavigate();
  const currentUser = useUserStore((state) => state.userInfo);
  const { confirm, confirmDialog } = useConfirmDialog();
  const sessionKey = `chat-group:${roomId}`;

  const [room, setRoom] = useState<ChatGroupRead | null>(null);
  const [characters, setCharacters] = useState<CharacterRead[]>([]);
  const [providers, setProviders] = useState<ModelProviderRead[]>([]);
  const [availableTags, setAvailableTags] = useState<TagRead[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [isUpdatingTags, setIsUpdatingTags] = useState(false);
  const [addTagValue, setAddTagValue] = useState("__add");
  const [members, setMembers] = useState<ChatGroupMemberRead[]>([]);
  const [userDirectory, setUserDirectory] = useState<AdminUserRead[]>([]);
  const [currentAiWakeup, setCurrentAiWakeup] = useState<WakeupTaskRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [memberDialog, setMemberDialog] = useState<MemberDialogState>({
    open: false,
    userId: "",
    role: "member",
  });

  const messaging = useWorkspaceMessagingController({
    sessionKey,
    isLoading,
    timezone: currentUser?.timezone || "UTC",
    currentUserId: currentUser?.uid || null,
    sendMessage: (payload) => sendChatGroupMessage(roomId, payload),
    mapOptimisticMessage: (message) => ({
      ...message,
      sender_user_id: currentUser?.uid || null,
    }),
  });

  const currentUserId = currentUser?.uid || null;
  const currentMembership = useMemo(
    () => members.find((item) => item.user_id === currentUserId) || null,
    [currentUserId, members],
  );
  const canManage = Boolean(
    currentUserId && room && (room.owner_user_id === currentUserId || currentMembership?.member_role === "admin"),
  );
  const characterName = useMemo(
    () => characters.find((item) => resolveActualId("character", item.id) === room?.character_id)?.name || t("unknownCharacter"),
    [characters, room, t],
  );
  const modelLabel = useMemo(() => {
    const resolved = resolveModelLabel(room, providers);
    return resolved === "Unknown model" ? t("unknownModel") : resolved;
  }, [providers, room, t]);
  const availableAddableTags = useMemo(
    () =>
      availableTags.filter(
        (item) =>
          !item.is_system &&
          !selectedTagIds.includes(item.id) &&
          (item.visibility_mode !== "group_acl" || item.visible_chat_group_ids.includes(roomId)),
      ),
    [availableTags, roomId, selectedTagIds],
  );
  const userChoices = useMemo(
    () => userDirectory.filter((item) => item.uid !== currentUserId),
    [currentUserId, userDirectory],
  );
  const memberNameMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const user of userDirectory) {
      map.set(user.uid, user.username);
    }
    if (currentUserId && currentUser?.username) {
      map.set(currentUserId, currentUser.username);
    }
    return map;
  }, [currentUser?.username, currentUserId, userDirectory]);

  useEffect(() => {
    if (!roomId.trim()) {
      toast.error(t("invalidId"));
      navigate("/chat-groups", { replace: true });
      return;
    }
    messaging.resetRuntimeSession();
    void loadWorkspace(true);
  }, [roomId]);

  const handleSocketEvent = createRuntimeWsEventHandler({
    sessionKey,
    upsertMessage: messaging.upsertMessage,
    setStreamingAssistant: messaging.setStreamingAssistant,
    appendStreamingAssistant: messaging.appendStreamingAssistant,
    applyStatePatch: messaging.applyStatePatch,
    setError: messaging.setError,
    reloadWorkspace: () => {
      void loadWorkspace(false);
    },
    reloadWakeups: () => {
      void loadCurrentAiWakeup();
    },
    scrollToBottom: messaging.scrollToBottom,
    onRoundFailed: (detail) => {
      toast.error(t("aiRequestFailed", { detail: localizeApiMessage(detail) }));
    },
  });

  useChatGroupWs({
    roomId,
    enabled: Boolean(roomId),
    onEvent: handleSocketEvent,
    onRecover: async () => {
      await loadWorkspace(false);
      toast.success(t("realtimeRestored"));
    },
    onError: (message) => {
      messaging.setError(sessionKey, localizeApiMessage(message));
    },
  });

  async function loadWorkspace(initial = false) {
    if (initial) {
      setIsLoading(true);
    }
    try {
      const [nextRoom, state, nextMembers, nextMessages, characterResponse, providerResponse, wakeups, tagItems] =
        await Promise.all([
          getChatGroup(roomId),
          getChatGroupState(roomId),
          listChatGroupMembers(roomId),
          listChatGroupMessages(roomId, null, 50),
          getCharacters(1, 100, "all"),
          listModelProviders(1, 100),
          listChatGroupWakeups(roomId, { status: "queued", only_ai: true, limit: 1 }),
          listTags(),
        ]);

      setRoom(nextRoom);
      setMembers(nextMembers);
      setCharacters(characterResponse.items);
      setProviders(providerResponse.items);
      setAvailableTags(tagItems);
      setSelectedTagIds(
        tagItems
          .filter((item) => !item.is_system && state.active_tags_json.includes(item.actual_id))
          .map((item) => item.id),
      );
      setCurrentAiWakeup(wakeups[0] || null);
      messaging.setMessages(sessionKey, nextMessages.items);
      setHasMore(Boolean(nextMessages.has_more));
      messaging.applyStatePatch(sessionKey, {
        relationScore: state.relation_score,
        personaJson: state.persona_json,
        activeTags: state.active_tags_json,
        currentWakeupTaskId: state.current_wakeup_task_id,
        dispatchState: "idle",
        dispatchReason: null,
      });
      messaging.setError(sessionKey, null);

      if (currentUser?.permissions?.["users:read"]) {
        try {
          const users = await listAdminUsers(1, 200);
          setUserDirectory(users.items);
        } catch {
          setUserDirectory([]);
        }
      }
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("workspaceLoadFailed"));
      navigate("/chat-groups", { replace: true });
    } finally {
      setIsLoading(false);
    }
  }

  async function loadOlderMessages() {
    if (isLoadingMore || !messaging.visibleMessages.length) {
      return;
    }
    setIsLoadingMore(true);
    try {
      const oldestId = messaging.visibleMessages[0]?.message_uid ?? null;
      const response = await listChatGroupMessages(roomId, oldestId, 50);
      messaging.prependMessages(sessionKey, response.items);
      setHasMore(Boolean(response.has_more));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("workspaceLoadFailed"));
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function handleRetractMessage(message: MessageRead) {
    try {
      await retractChatGroupMessage(roomId, message.message_uid);
      await loadWorkspace(false);
      toast.success(t("messageRetracted"));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("messageRetractFailed"));
    }
  }

  async function loadCurrentAiWakeup() {
    try {
      const wakeups = await listChatGroupWakeups(roomId, { status: "queued", only_ai: true, limit: 1 });
      setCurrentAiWakeup(wakeups[0] || null);
    } catch (error) {
      console.error(error);
    }
  }

  async function handleAddMember() {
    if (!memberDialog.userId.trim()) {
      return;
    }
    try {
      await addChatGroupMember(roomId, memberDialog.userId, memberDialog.role);
      setMemberDialog({ open: false, userId: "", role: "member" });
      await loadWorkspace(false);
      toast.success(t("memberAdded"));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("memberAddFailed"));
    }
  }

  async function handleChangeMemberRole(member: ChatGroupMemberRead, nextRole: "member" | "admin") {
    try {
      await updateChatGroupMember(roomId, member.user_id, nextRole);
      await loadWorkspace(false);
      toast.success(t("memberUpdated"));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("memberUpdateFailed"));
    }
  }

  async function handleRemoveMember(member: ChatGroupMemberRead) {
    const accepted = await confirm({
      title: t("removeMember"),
      description: t("removeMemberConfirm", { name: memberNameMap.get(member.user_id) || member.user_id }),
      confirmLabel: t("removeMember"),
      cancelLabel: t("common.cancel", { defaultValue: "Cancel" }),
      variant: "destructive",
    });
    if (!accepted) {
      return;
    }
    try {
      await removeChatGroupMember(roomId, member.user_id);
      await loadWorkspace(false);
      toast.success(t("memberRemoved"));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("memberRemoveFailed"));
    }
  }

  async function persistTagIds(nextTagIds: number[]) {
    if (isUpdatingTags) {
      return;
    }
    const normalized = Array.from(new Set(nextTagIds)).sort((a, b) => a - b);
    const previousIds = selectedTagIds;
    setIsUpdatingTags(true);
    setSelectedTagIds(normalized);
    try {
      const tags = await bindChatGroupTags(roomId, normalized);
      messaging.applyStatePatch(sessionKey, { activeTags: tags.map((item) => item.actual_id) });
      setSelectedTagIds(tags.filter((item) => !item.is_system).map((item) => item.id));
    } catch (error) {
      setSelectedTagIds(previousIds);
      console.error(error);
      showErrorToast(error, t("workspaceLoadFailed"));
    } finally {
      setIsUpdatingTags(false);
      setAddTagValue("__add");
    }
  }

  async function handleAddTag(value: string) {
    setAddTagValue(value);
    if (value === "__add") {
      return;
    }
    const tagId = Number(value);
    if (!Number.isFinite(tagId)) {
      setAddTagValue("__add");
      return;
    }
    await persistTagIds([...selectedTagIds, tagId]);
  }

  function canRetractMessage(message: MessageRead) {
    if (message.is_retracted) {
      return false;
    }
    if (canManage) {
      return true;
    }
    return message.role === "user" && message.sender_user_id === currentUserId;
  }

  function displaySenderName(message: MessageRead) {
    if (message.role !== "user") {
      return t("assistant");
    }
    if (!message.sender_user_id) {
      return t("member");
    }
    if (message.sender_user_id === currentUserId) {
      return t("you");
    }
    return memberNameMap.get(message.sender_user_id) || message.sender_user_id;
  }

  return {
    room,
    characters,
    providers,
    availableTags,
    selectedTagIds,
    isUpdatingTags,
    addTagValue,
    members,
    userDirectory,
    messageInput: messaging.messageInput,
    currentAiWakeup,
    isLoading,
    isLoadingMore,
    isSending: messaging.isSending,
    hasMore,
    memberDialog,
    confirmDialog,
    session: messaging.session,
    viewportRef: messaging.viewportRef,
    visibleMessages: messaging.visibleMessages,
    currentUserId,
    currentMembership,
    canManage,
    characterName,
    modelLabel,
    availableAddableTags,
    userChoices,
    memberNameMap,
    onMessageInputChange: messaging.onMessageInputChange,
    handleSendMessage: messaging.handleSendMessage,
    loadWorkspace,
    loadOlderMessages,
    handleRetractMessage,
    handleAddMember,
    handleChangeMemberRole,
    handleRemoveMember,
    persistTagIds,
    handleAddTag,
    canRetractMessage,
    displaySenderName,
    setMemberDialog,
  };
}
