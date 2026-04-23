import type { RefObject } from "react";
import { ChevronUp, Loader2, MessageSquareOff } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MessageRead } from "@/api/types/chat";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatWorkspaceTime } from "@/features/workspace/utils";

type ChatGroupTimelineProps = {
  isLoading: boolean;
  hasMore: boolean;
  isLoadingMore: boolean;
  messages: MessageRead[];
  streamingAssistant: string;
  currentUserId: string | null;
  viewportRef?: RefObject<HTMLDivElement | null>;
  canRetractMessage: (message: MessageRead) => boolean;
  displaySenderName: (message: MessageRead) => string;
  onLoadOlderMessages: () => void;
  onRetractMessage: (message: MessageRead) => void;
};

export function ChatGroupTimeline({
  isLoading,
  hasMore,
  isLoadingMore,
  messages,
  streamingAssistant,
  currentUserId,
  viewportRef,
  canRetractMessage,
  displaySenderName,
  onLoadOlderMessages,
  onRetractMessage,
}: ChatGroupTimelineProps) {
  const { t } = useTranslation(["chatGroups", "workspace"]);

  return (
    <div ref={viewportRef} className="flex-1 overflow-auto rounded-[32px] border border-border/70 bg-background/60 p-4">
      {isLoading ? (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">{t("loadingTimeline")}</div>
      ) : (
        <div className="space-y-4">
          {hasMore ? (
            <div className="flex justify-center">
              <Button variant="outline" size="sm" disabled={isLoadingMore} onClick={onLoadOlderMessages}>
                {isLoadingMore ? <Loader2 className="mr-2 size-4 animate-spin" /> : <ChevronUp className="mr-2 size-4" />}
                {t("workspace:loadOlderMessages")}
              </Button>
            </div>
          ) : null}
          {messages.map((message) => {
            const isSelf = message.role === "user" && message.sender_user_id === currentUserId;
            const isAssistant = message.role !== "user";
            const bubbleClass = isAssistant
              ? "border-cyan-500/20 bg-cyan-500/6"
              : isSelf
                ? "border-orange-500/25 bg-orange-500/10"
                : "border-border/70 bg-card";
            return (
              <div key={message.id} className={`flex ${isSelf ? "justify-end" : "justify-start"}`}>
                <div className={`max-w-[92%] rounded-[26px] border px-4 py-3 shadow-sm ${bubbleClass}`}>
                  <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span>{displaySenderName(message)}</span>
                    <span>{formatWorkspaceTime(message.created_at)}</span>
                    {message.is_retracted ? <Badge variant="destructive">{t("retracted")}</Badge> : null}
                    {canRetractMessage(message) ? (
                      <Button variant="ghost" size="sm" className="h-6 px-2 text-xs" onClick={() => onRetractMessage(message)}>
                        <MessageSquareOff className="mr-1 size-3" />
                        {t("retract")}
                      </Button>
                    ) : null}
                  </div>
                  <div className="whitespace-pre-wrap text-sm leading-6">
                    {message.is_retracted ? (
                      <span className="italic text-muted-foreground">
                        {message.retraction_note
                          ? t("retractedMessageWithNote", { note: message.retraction_note })
                          : t("retractedMessage")}
                      </span>
                    ) : (
                      message.content
                    )}
                  </div>
                </div>
              </div>
            );
          })}
          {streamingAssistant ? (
            <div className="flex justify-start">
              <div className="max-w-[92%] rounded-[26px] border border-dashed border-cyan-500/35 bg-cyan-500/6 px-4 py-3">
                <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                  <span>{t("assistant")}</span>
                  <Badge variant="outline">{t("streaming")}</Badge>
                </div>
                <div className="whitespace-pre-wrap text-sm leading-6">{streamingAssistant}</div>
              </div>
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
