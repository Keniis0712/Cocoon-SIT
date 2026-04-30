import { ArrowLeft, Loader2, MemoryStick, RefreshCcw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useNavigate, useParams } from "react-router-dom";

import PageFrame from "@/components/PageFrame";
import { Button } from "@/components/ui/button";
import { CocoonConversationPanel } from "@/features/cocoons/components/CocoonConversationPanel";
import { CocoonSessionPanel } from "@/features/cocoons/components/CocoonSessionPanel";
import { useCocoonWorkspaceController } from "@/features/cocoons/hooks/useCocoonWorkspaceController";

export default function CocoonWorkspacePage() {
  const { t } = useTranslation("workspace");
  const navigate = useNavigate();
  const params = useParams();
  const cocoonId = Number(params.cocoonId);

  const controller = useCocoonWorkspaceController(cocoonId);

  return (
    <PageFrame
      title={controller.selectedCocoon?.name || t("defaultTitle")}
      actions={
        <>
          <Button variant="outline" onClick={() => navigate("/cocoons")}>
            <ArrowLeft className="mr-2 size-4" />
            {t("backToCocoons")}
          </Button>
          <Button variant="outline" onClick={() => navigate(`/cocoons/${cocoonId}/memories`)}>
            <MemoryStick className="mr-2 size-4" />
            {t("memoriesTitle")}
          </Button>
          <Button
            variant="outline"
            onClick={() => void controller.handleCompactContext()}
            disabled={controller.isCompacting || controller.isLoading}
          >
            {controller.isCompacting ? (
              <Loader2 className="mr-2 size-4 animate-spin" />
            ) : (
              <RefreshCcw className="mr-2 size-4" />
            )}
            {t("compressContext")}
          </Button>
          <Button variant="outline" onClick={() => void controller.handleRetryReply()}>
            <RefreshCcw className="mr-2 size-4" />
            {t("retryReply")}
          </Button>
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-[1.7fr_0.95fr]">
        <CocoonConversationPanel
          viewportRef={controller.viewportRef}
          isLoading={controller.isLoading}
          hasMore={controller.hasMore}
          isLoadingMore={controller.isLoadingMore}
          visibleMessages={controller.visibleMessages}
          streamingAssistant={controller.session?.streamingAssistant || ""}
          messageInput={controller.messageInput}
          isSending={controller.isSending}
          onLoadOlderMessages={() => void controller.loadOlderMessages()}
          onMessageInputChange={controller.onMessageInputChange}
          onSendMessage={() => void controller.handleSendMessage()}
        />

        <div className="order-2 space-y-4">
          <CocoonSessionPanel
            selectedCocoon={controller.selectedCocoon}
            providerModels={controller.providerModels}
            sessionActiveTags={controller.session?.activeTags || []}
            selectedTagIds={controller.selectedTagIds}
            availableAddableTags={controller.availableAddableTags}
            addTagValue={controller.addTagValue}
            isUpdatingTags={controller.isUpdatingTags}
            currentModelId={controller.session?.currentModelId}
            dispatchState={controller.session?.dispatchState}
            relationScore={controller.session?.relationScore}
            currentAiWakeup={controller.currentAiWakeup}
            debounceUntil={controller.session?.debounceUntil}
            dispatchReason={controller.session?.dispatchReason}
            lastError={controller.session?.lastError}
            onRemoveTag={(tagId) =>
              void controller.persistTagIds(controller.selectedTagIds.filter((id) => id !== tagId))
            }
            onAddTag={(value) => void controller.handleAddTag(value)}
            onChangeModel={(modelId) => void controller.handleChangeModel(modelId)}
          />
        </div>
      </div>
    </PageFrame>
  );
}
