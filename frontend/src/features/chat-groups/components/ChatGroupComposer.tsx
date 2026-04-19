import { Loader2, Send } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type ChatGroupComposerProps = {
  messageInput: string;
  isSending: boolean;
  isLoading: boolean;
  dispatchState: string | null | undefined;
  onChange: (value: string) => void;
  onSend: () => void;
};

export function ChatGroupComposer({
  messageInput,
  isSending,
  isLoading,
  dispatchState,
  onChange,
  onSend,
}: ChatGroupComposerProps) {
  const { t } = useTranslation("chatGroups");

  return (
    <div className="rounded-[28px] border border-border/70 bg-background/70 p-3">
      <Textarea
        rows={4}
        placeholder={t("writeMessagePlaceholder")}
        value={messageInput}
        disabled={isSending || isLoading}
        onChange={(event) => onChange(event.target.value)}
      />
      <div className="mt-3 flex items-center justify-between gap-2">
        <div className="text-xs text-muted-foreground">
          {dispatchState === "queued" || dispatchState === "running"
            ? t("composerDispatchHint", { state: dispatchState })
            : t("composerSharedHint")}
        </div>
        <Button disabled={!messageInput.trim() || isSending || isLoading} onClick={onSend}>
          {isSending ? <Loader2 className="mr-2 size-4 animate-spin" /> : <Send className="mr-2 size-4" />}
          {t("send")}
        </Button>
      </div>
    </div>
  );
}
