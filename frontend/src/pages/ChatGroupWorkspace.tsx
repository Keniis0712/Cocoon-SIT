import { ArrowLeft, RefreshCcw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import PageFrame from "@/components/PageFrame";
import { Button } from "@/components/ui/button";
import { ChatGroupComposer } from "@/features/chat-groups/components/ChatGroupComposer";
import { ChatGroupMemberDialog } from "@/features/chat-groups/components/ChatGroupDialogs";
import { ChatGroupSidebar } from "@/features/chat-groups/components/ChatGroupSidebar";
import { ChatGroupTimeline } from "@/features/chat-groups/components/ChatGroupTimeline";
import { useChatGroupWorkspaceController } from "@/features/chat-groups/hooks/useChatGroupWorkspaceController";

export default function ChatGroupWorkspacePage() {
  const { t } = useTranslation("chatGroups");
  const navigate = useNavigate();
  const { roomId = "" } = useParams();

  const controller = useChatGroupWorkspaceController(roomId);

  return (
    <PageFrame
      title={controller.room?.name || t("title")}
      actions={
        <>
          <Button variant="outline" onClick={() => navigate("/chat-groups")}>
            <ArrowLeft className="mr-2 size-4" />
            {t("backToRooms")}
          </Button>
          <Button variant="outline" onClick={() => void controller.loadWorkspace(false)}>
            <RefreshCcw className="mr-2 size-4" />
            {t("refreshRooms")}
          </Button>
        </>
      }
    >
      {controller.confirmDialog}
      <div className="grid gap-4 xl:grid-cols-[1.6fr_0.9fr]">
        <div className="min-h-[78vh] overflow-hidden rounded-xl border border-border/70 bg-card/90">
          <div className="border-b border-border/70 bg-linear-to-r from-cyan-500/12 via-orange-500/8 to-transparent px-4 py-4">
            <div className="font-heading text-base leading-snug font-medium">{t("roomTimelineTitle")}</div>
          </div>
          <div className="flex h-[calc(78vh-5rem)] flex-col gap-4 p-4">
            <ChatGroupTimeline
              viewportRef={controller.viewportRef}
              isLoading={controller.isLoading}
              hasMore={controller.hasMore}
              isLoadingMore={controller.isLoadingMore}
              messages={controller.visibleMessages}
              streamingAssistant={controller.session?.streamingAssistant || ""}
              currentUserId={controller.currentUserId}
              canRetractMessage={controller.canRetractMessage}
              displaySenderName={controller.displaySenderName}
              onLoadOlderMessages={() => void controller.loadOlderMessages()}
              onRetractMessage={(message) => void controller.handleRetractMessage(message)}
            />

            <ChatGroupComposer
              messageInput={controller.messageInput}
              isSending={controller.isSending}
              isLoading={controller.isLoading}
              dispatchState={controller.session?.dispatchState}
              onChange={controller.onMessageInputChange}
              onSend={() => void controller.handleSendMessage()}
            />
          </div>
        </div>

        <ChatGroupSidebar
          characterName={controller.characterName}
          modelLabel={controller.modelLabel}
          roomTags={controller.availableTags.filter((item) => controller.selectedTagIds.includes(item.id))}
          sessionActiveTags={controller.session?.activeTags || []}
          availableAddableTags={controller.availableAddableTags}
          addTagValue={controller.addTagValue}
          isUpdatingTags={controller.isUpdatingTags}
          dispatchState={controller.session?.dispatchState}
          relationScore={controller.session?.relationScore}
          currentAiWakeup={controller.currentAiWakeup}
          debounceUntil={controller.session?.debounceUntil}
          lastError={controller.session?.lastError}
          members={controller.members}
          canManage={controller.canManage}
          ownerUserId={controller.room?.owner_user_id}
          memberNameMap={controller.memberNameMap}
          onAddTag={(value) => void controller.handleAddTag(value)}
          onRemoveTag={(tagId) =>
            void controller.persistTagIds(controller.selectedTagIds.filter((item) => item !== tagId))
          }
          onOpenAddMember={() =>
            controller.setMemberDialog({ open: true, userId: "", role: "member" })
          }
          onToggleMemberRole={(member, nextRole) =>
            void controller.handleChangeMemberRole(member, nextRole)
          }
          onRemoveMember={(member) => void controller.handleRemoveMember(member)}
        />
      </div>

      <ChatGroupMemberDialog
        open={controller.memberDialog.open}
        userId={controller.memberDialog.userId}
        role={controller.memberDialog.role}
        userChoices={controller.userChoices}
        onOpenChange={(open) => controller.setMemberDialog((prev) => ({ ...prev, open }))}
        onUserIdChange={(value) => controller.setMemberDialog((prev) => ({ ...prev, userId: value }))}
        onRoleChange={(value) => controller.setMemberDialog((prev) => ({ ...prev, role: value }))}
        onSubmit={() => void controller.handleAddMember()}
        onCancel={() => controller.setMemberDialog({ open: false, userId: "", role: "member" })}
      />
    </PageFrame>
  );
}
