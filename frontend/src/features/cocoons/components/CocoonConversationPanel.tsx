import type { RefObject } from "react";
import { ChevronUp, Loader2 } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { MessageRead } from "@/api/types/chat";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { formatWorkspaceTime } from "@/features/workspace/utils";

type CocoonConversationPanelProps = {
  isLoading: boolean;
  hasMore: boolean;
  isLoadingMore: boolean;
  visibleMessages: MessageRead[];
  streamingAssistant: string;
  messageInput: string;
  isSending: boolean;
  viewportRef?: RefObject<HTMLDivElement | null>;
  onLoadOlderMessages: () => void;
  onMessageInputChange: (value: string) => void;
  onSendMessage: () => void;
};

export function CocoonConversationPanel({
  isLoading,
  hasMore,
  isLoadingMore,
  visibleMessages,
  streamingAssistant,
  messageInput,
  isSending,
  viewportRef,
  onLoadOlderMessages,
  onMessageInputChange,
  onSendMessage,
}: CocoonConversationPanelProps) {
  const { t } = useTranslation(["workspace", "common", "chatGroups"]);

  return (
    <Card className="order-1 min-h-[78vh] border-border/70 bg-card/90">
      <CardHeader>
        <CardTitle>{t("workspace:chatTitle")}</CardTitle>
        <CardDescription>{t("workspace:chatLoadingDescription")}</CardDescription>
      </CardHeader>
      <CardContent className="flex h-[calc(78vh-5rem)] flex-col gap-4">
        <div ref={viewportRef} className="flex-1 overflow-auto rounded-[28px] border border-border/70 bg-background/60 p-4">
          {isLoading ? (
            <div className="flex h-full items-center justify-center text-sm text-muted-foreground">{t("workspace:loadingMessages")}</div>
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
              {visibleMessages.length === 0 ? (
                <div className="rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
                  {t("workspace:emptyMessages")}
                </div>
              ) : null}
              {visibleMessages.map((message) => {
                const isUser = message.role === "user";
                return (
                  <div key={message.id} className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
                    <div
                      className={`max-w-[88%] rounded-[24px] border px-4 py-3 shadow-sm ${isUser ? "border-primary/30 bg-primary/10" : "border-border/70 bg-card"}`}
                    >
                      <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                        <span>{isUser ? t("common:user") : t("common:assistant")}</span>
                        <span>{formatWorkspaceTime(message.created_at)}</span>
                      </div>
                      <div className="whitespace-pre-wrap text-sm leading-6">{message.content}</div>
                    </div>
                  </div>
                );
              })}
              {streamingAssistant ? (
                <div className="flex justify-start">
                  <div className="max-w-[88%] rounded-[24px] border border-dashed border-primary/40 bg-primary/5 px-4 py-3">
                    <div className="mb-2 flex items-center gap-2 text-xs text-muted-foreground">
                      <span>{t("common:assistant")}</span>
                      <Badge variant="outline">{t("chatGroups:streaming")}</Badge>
                    </div>
                    <div className="whitespace-pre-wrap text-sm leading-6">{streamingAssistant}</div>
                  </div>
                </div>
              ) : null}
            </div>
          )}
        </div>

        <div className="rounded-[28px] border border-border/70 bg-background/70 p-3">
          <Textarea
            rows={4}
            placeholder={t("workspace:inputPlaceholder")}
            value={messageInput}
            disabled={isSending || isLoading}
            onChange={(event) => onMessageInputChange(event.target.value)}
          />
          <div className="mt-3 flex items-center justify-between gap-2">
            <div />
            <Button disabled={!messageInput.trim() || isSending || isLoading} onClick={onSendMessage}>
              {isSending ? <Loader2 className="mr-2 size-4 animate-spin" /> : null}
              {t("workspace:send")}
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
