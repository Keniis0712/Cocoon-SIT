import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowLeft,
  RefreshCcw,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { showErrorToast } from "@/api/client";
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
import { resolveActualId } from "@/api/id-map";
import { listModelProviders } from "@/api/providers";
import { bindChatGroupTags, listTags } from "@/api/tags";
import { listAdminUsers } from "@/api/admin-users";
import type { AdminUserRead } from "@/api/types/access";
import type { CharacterRead } from "@/api/types/catalog";
import type { TagRead } from "@/api/types/catalog";
import type { MessageRead } from "@/api/types/chat";
import type { ChatGroupMemberRead, ChatGroupRead } from "@/api/types/chat-groups";
import type { ModelProviderRead } from "@/api/types/providers";
import type { WakeupTaskRead } from "@/api/types/wakeups";
import { listChatGroupWakeups } from "@/api/wakeups";
import PageFrame from "@/components/PageFrame";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ChatGroupComposer } from "@/features/chat-groups/components/ChatGroupComposer";
import { ChatGroupMemberDialog } from "@/features/chat-groups/components/ChatGroupDialogs";
import { ChatGroupSidebar } from "@/features/chat-groups/components/ChatGroupSidebar";
import { ChatGroupTimeline } from "@/features/chat-groups/components/ChatGroupTimeline";
import { createRuntimeWsEventHandler } from "@/features/workspace/runtimeWsEvents";
import { useChatGroupWs } from "@/hooks/useChatGroupWs";
import { useChatSessionStore } from "@/store/useChatSessionStore";
import { useUserStore } from "@/store/useUserStore";

type MemberDialogState = {
  open: boolean;
  userId: string;
  role: "member" | "admin";
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

export default function ChatGroupWorkspacePage() {
  const { t } = useTranslation("chatGroups");
  const navigate = useNavigate();
  const { roomId = "" } = useParams();
  const viewportRef = useRef<HTMLDivElement | null>(null);
  const typingStartedAtRef = useRef<number | null>(null);
  const hasAutoScrolledRef = useRef(false);
  const sessionKey = `chat-group:${roomId}`;
  const currentUser = useUserStore((state) => state.userInfo);

  const [room, setRoom] = useState<ChatGroupRead | null>(null);
  const [characters, setCharacters] = useState<CharacterRead[]>([]);
  const [providers, setProviders] = useState<ModelProviderRead[]>([]);
  const [availableTags, setAvailableTags] = useState<TagRead[]>([]);
  const [selectedTagIds, setSelectedTagIds] = useState<number[]>([]);
  const [isUpdatingTags, setIsUpdatingTags] = useState(false);
  const [addTagValue, setAddTagValue] = useState("__add");
  const [members, setMembers] = useState<ChatGroupMemberRead[]>([]);
  const [userDirectory, setUserDirectory] = useState<AdminUserRead[]>([]);
  const [messageInput, setMessageInput] = useState("");
  const [currentAiWakeup, setCurrentAiWakeup] = useState<WakeupTaskRead | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [hasMore, setHasMore] = useState(false);
  const [memberDialog, setMemberDialog] = useState<MemberDialogState>({ open: false, userId: "", role: "member" });

  const session = useChatSessionStore((state) => state.sessions[sessionKey] ?? null);
  const ensureSession = useChatSessionStore((state) => state.ensureSession);
  const resetSession = useChatSessionStore((state) => state.resetSession);
  const setMessages = useChatSessionStore((state) => state.setMessages);
  const prependMessages = useChatSessionStore((state) => state.prependMessages);
  const upsertMessage = useChatSessionStore((state) => state.upsertMessage);
  const setStreamingAssistant = useChatSessionStore((state) => state.setStreamingAssistant);
  const appendStreamingAssistant = useChatSessionStore((state) => state.appendStreamingAssistant);
  const applyStatePatch = useChatSessionStore((state) => state.applyStatePatch);
  const setTyping = useChatSessionStore((state) => state.setTyping);
  const setError = useChatSessionStore((state) => state.setError);

  const currentUserId = currentUser?.uid || null;
  const currentMembership = useMemo(
    () => members.find((item) => item.user_id === currentUserId) || null,
    [currentUserId, members],
  );
  const canManage = Boolean(currentUserId && room && (room.owner_user_id === currentUserId || currentMembership?.member_role === "admin"));
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
  const visibleMessages = useMemo(() => (session?.messages || []).filter((item) => !item.is_thought), [session?.messages]);
  const userChoices = useMemo(() => userDirectory.filter((item) => item.uid !== currentUserId), [currentUserId, userDirectory]);
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
    ensureSession(sessionKey);
    resetSession(sessionKey);
    hasAutoScrolledRef.current = false;
    void loadWorkspace(true);
  }, [roomId]);

  const handleSocketEvent = createRuntimeWsEventHandler({
    sessionKey,
    upsertMessage,
    setStreamingAssistant,
    appendStreamingAssistant,
    applyStatePatch,
    setError,
    reloadWorkspace: () => {
      void loadWorkspace(false);
    },
    reloadWakeups: () => {
      void loadCurrentAiWakeup();
    },
    scrollToBottom: () => {
      if (viewportRef.current) {
        viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
      }
    },
    onRoundFailed: (detail) => {
      toast.error(t("aiRequestFailed", { detail }));
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
      setError(sessionKey, message);
    },
  });

  useEffect(() => {
    if (!viewportRef.current) {
      return;
    }
    if (!isLoading && visibleMessages.length > 0 && !hasAutoScrolledRef.current) {
      requestAnimationFrame(() => {
        if (viewportRef.current) {
          viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
        }
      });
      hasAutoScrolledRef.current = true;
    }
  }, [isLoading, visibleMessages.length]);

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
      setMessages(sessionKey, nextMessages.items);
      setHasMore(Boolean(nextMessages.has_more));
      applyStatePatch(sessionKey, {
        relationScore: state.relation_score,
        personaJson: state.persona_json,
        activeTags: state.active_tags_json,
        currentWakeupTaskId: state.current_wakeup_task_id,
        dispatchState: "idle",
        dispatchReason: null,
      });
      setError(sessionKey, null);

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
    if (isLoadingMore || !visibleMessages.length) {
      return;
    }
    setIsLoadingMore(true);
    try {
      const oldestId = visibleMessages[0]?.message_uid ?? null;
      const response = await listChatGroupMessages(roomId, oldestId, 50);
      prependMessages(sessionKey, response.items);
      setHasMore(Boolean(response.has_more));
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("workspaceLoadFailed"));
    } finally {
      setIsLoadingMore(false);
    }
  }

  async function handleSendMessage() {
    if (!messageInput.trim() || isSending) {
      return;
    }

    const content = messageInput.trim();
    const now = Date.now();
    const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || null;
    const recentTurnCount = visibleMessages.slice(-8).length;
    const lastMessageAt = visibleMessages.length ? new Date(visibleMessages[visibleMessages.length - 1].created_at).getTime() : null;
    const idleSeconds = lastMessageAt ? Math.max(0, Math.floor((now - lastMessageAt) / 1000)) : null;
    const typingHint = typingStartedAtRef.current ? Math.max(0, now - typingStartedAtRef.current) : null;

    setIsSending(true);
    setTyping(sessionKey, false);
    setError(sessionKey, null);
    try {
      const result = await sendChatGroupMessage(roomId, {
        content,
        client_request_id: window.crypto?.randomUUID?.() || `${Date.now()}`,
        client_sent_at: new Date(now).toISOString(),
        timezone,
        locale: navigator.language || null,
        recent_turn_count: recentTurnCount,
        idle_seconds: idleSeconds,
        typing_hint_ms: typingHint,
      });
      upsertMessage(sessionKey, {
        ...result.user_message,
        sender_user_id: currentUserId,
      });
      applyStatePatch(sessionKey, {
        dispatchState: result.dispatch_status,
        dispatchReason: null,
        debounceUntil: result.debounce_until,
      });
      setMessageInput("");
      typingStartedAtRef.current = null;
      queueMicrotask(() => {
        if (viewportRef.current) {
          viewportRef.current.scrollTop = viewportRef.current.scrollHeight;
        }
      });
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("messageSendFailed"));
    } finally {
      setIsSending(false);
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
    if (!window.confirm(t("removeMemberConfirm", { name: memberNameMap.get(member.user_id) || member.user_id }))) {
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
      applyStatePatch(sessionKey, { activeTags: tags.map((item) => item.actual_id) });
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

  return (
    <PageFrame
      title={room?.name || t("title")}
      actions={
        <>
          <Button variant="outline" onClick={() => navigate("/chat-groups")}>
            <ArrowLeft className="mr-2 size-4" />
            {t("backToRooms")}
          </Button>
          <Button variant="outline" onClick={() => void loadWorkspace(false)}>
            <RefreshCcw className="mr-2 size-4" />
            {t("refreshRooms")}
          </Button>
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[1.6fr_0.9fr]">
        <Card className="min-h-[78vh] overflow-hidden border-border/70 bg-card/90">
          <div className="border-b border-border/70 bg-linear-to-r from-cyan-500/12 via-orange-500/8 to-transparent">
            <CardHeader>
              <CardTitle>{t("roomTimelineTitle")}</CardTitle>
            </CardHeader>
          </div>
          <CardContent className="flex h-[calc(78vh-5rem)] flex-col gap-4 p-4">
            <ChatGroupTimeline
              viewportRef={viewportRef}
              isLoading={isLoading}
              hasMore={hasMore}
              isLoadingMore={isLoadingMore}
              messages={visibleMessages}
              streamingAssistant={session?.streamingAssistant || ""}
              currentUserId={currentUserId}
              canRetractMessage={canRetractMessage}
              displaySenderName={displaySenderName}
              onLoadOlderMessages={() => void loadOlderMessages()}
              onRetractMessage={(message) => void handleRetractMessage(message)}
            />

            <ChatGroupComposer
              messageInput={messageInput}
              isSending={isSending}
              isLoading={isLoading}
              dispatchState={session?.dispatchState}
              onChange={(value) => {
                if (!typingStartedAtRef.current) {
                  typingStartedAtRef.current = Date.now();
                }
                setTyping(sessionKey, true);
                setMessageInput(value);
              }}
              onSend={() => void handleSendMessage()}
            />
          </CardContent>
        </Card>

        <ChatGroupSidebar
          characterName={characterName}
          modelLabel={modelLabel}
          roomTags={availableTags.filter((item) => selectedTagIds.includes(item.id))}
          sessionActiveTags={session?.activeTags || []}
          availableAddableTags={availableAddableTags}
          addTagValue={addTagValue}
          isUpdatingTags={isUpdatingTags}
          dispatchState={session?.dispatchState}
          relationScore={session?.relationScore}
          currentAiWakeup={currentAiWakeup}
          debounceUntil={session?.debounceUntil}
          lastError={session?.lastError}
          members={members}
          canManage={canManage}
          ownerUserId={room?.owner_user_id}
          memberNameMap={memberNameMap}
          onAddTag={(value) => void handleAddTag(value)}
          onRemoveTag={(tagId) => void persistTagIds(selectedTagIds.filter((item) => item !== tagId))}
          onOpenAddMember={() => setMemberDialog({ open: true, userId: "", role: "member" })}
          onToggleMemberRole={(member, nextRole) => void handleChangeMemberRole(member, nextRole)}
          onRemoveMember={(member) => void handleRemoveMember(member)}
        />
      </div>

      <ChatGroupMemberDialog
        open={memberDialog.open}
        userId={memberDialog.userId}
        role={memberDialog.role}
        userChoices={userChoices}
        onOpenChange={(open) => setMemberDialog((prev) => ({ ...prev, open }))}
        onUserIdChange={(value) => setMemberDialog((prev) => ({ ...prev, userId: value }))}
        onRoleChange={(value) => setMemberDialog((prev) => ({ ...prev, role: value }))}
        onSubmit={() => void handleAddMember()}
        onCancel={() => setMemberDialog({ open: false, userId: "", role: "member" })}
      />
    </PageFrame>
  );
}
