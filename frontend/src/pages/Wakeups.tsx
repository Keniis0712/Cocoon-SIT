import { useEffect, useMemo, useState } from "react";
import { BellRing, RefreshCcw } from "lucide-react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";

import { showErrorToast } from "@/api/client";
import { listAuditWakeups } from "@/api/wakeups";
import { resolveActualId } from "@/api/id-map";
import type { WakeupTargetType, WakeupTaskRead } from "@/api/types/wakeups";
import AccessCard from "@/components/AccessCard";
import PageFrame from "@/components/PageFrame";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatWorkspaceTime } from "@/features/workspace/utils";
import { useUserStore } from "@/store/useUserStore";

export default function WakeupsPage() {
  const { t } = useTranslation(["wakeups", "common"]);
  const userInfo = useUserStore((state) => state.userInfo);
  const [searchParams] = useSearchParams();
  const canAudit = Boolean(userInfo?.can_audit);
  const [items, setItems] = useState<WakeupTaskRead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [status, setStatus] = useState(searchParams.get("status") || "all");
  const [targetType, setTargetType] = useState<WakeupTargetType | "all">(
    (searchParams.get("targetType") as WakeupTargetType | "all") || "all",
  );
  const [onlyAi, setOnlyAi] = useState(true);
  const scopedTargetId = useMemo(() => {
    const targetId = searchParams.get("targetId");
    if (!targetId) {
      return undefined;
    }
    if (targetType === "cocoon") {
      return resolveActualId("cocoon", Number(targetId));
    }
    return targetId;
  }, [searchParams, targetType]);

  useEffect(() => {
    if (!canAudit) {
      return;
    }
    void loadWakeups();
  }, [canAudit, status, targetType, onlyAi]);

  async function loadWakeups() {
    setIsLoading(true);
    try {
      const wakeups = await listAuditWakeups({
        status: status !== "all" ? status : undefined,
        target_type: targetType !== "all" ? targetType : undefined,
        target_id: targetType !== "all" ? scopedTargetId : undefined,
        only_ai: onlyAi,
        limit: 200,
      });
      setItems(wakeups);
    } catch (error) {
      console.error(error);
      showErrorToast(error, t("wakeups:loadFailed"));
    } finally {
      setIsLoading(false);
    }
  }

  const groupedSummary = useMemo(() => {
    return {
      queued: items.filter((item) => item.status === "queued").length,
      cancelled: items.filter((item) => item.status === "cancelled").length,
      ai: items.filter((item) => item.is_ai_wakeup).length,
    };
  }, [items]);

  if (!canAudit) {
    return <AccessCard description={t("wakeups:noPermission")} />;
  }

  return (
    <PageFrame
      title={t("wakeups:title")}
      description={t("wakeups:description")}
      actions={
        <Button variant="outline" onClick={() => void loadWakeups()}>
          <RefreshCcw className="mr-2 size-4" />
          {t("wakeups:refresh")}
        </Button>
      }
    >
      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-4">
          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <BellRing className="size-4 text-primary" />
                {t("wakeups:filtersTitle")}
              </CardTitle>
              <CardDescription>{t("wakeups:filtersDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-2">
                <Label>{t("common:status")}</Label>
                <Select value={status} onValueChange={setStatus}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t("common:all")}</SelectItem>
                    <SelectItem value="queued">{t("wakeups:statusQueued")}</SelectItem>
                    <SelectItem value="running">{t("wakeups:statusRunning")}</SelectItem>
                    <SelectItem value="completed">{t("wakeups:statusCompleted")}</SelectItem>
                    <SelectItem value="cancelled">{t("wakeups:statusCancelled")}</SelectItem>
                    <SelectItem value="failed">{t("wakeups:statusFailed")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t("wakeups:targetType")}</Label>
                <Select value={targetType} onValueChange={(value) => setTargetType(value as WakeupTargetType | "all")}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">{t("common:all")}</SelectItem>
                    <SelectItem value="cocoon">{t("wakeups:targetCocoon")}</SelectItem>
                    <SelectItem value="chat_group">{t("wakeups:targetChatGroup")}</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <label className="flex items-center gap-3 rounded-lg border border-border/70 px-3 py-3 text-sm">
                <Checkbox checked={onlyAi} onCheckedChange={(checked) => setOnlyAi(Boolean(checked))} />
                <span>{t("wakeups:onlyAi")}</span>
              </label>
            </CardContent>
          </Card>

          <Card className="border-border/70 bg-card/90">
            <CardHeader>
              <CardTitle className="text-base">{t("wakeups:summaryTitle")}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <div className="rounded-2xl border border-border/70 p-4 text-sm">
                <div className="text-muted-foreground">{t("wakeups:queuedCount")}</div>
                <div className="mt-2 text-xl font-semibold">{groupedSummary.queued}</div>
              </div>
              <div className="rounded-2xl border border-border/70 p-4 text-sm">
                <div className="text-muted-foreground">{t("wakeups:cancelledCount")}</div>
                <div className="mt-2 text-xl font-semibold">{groupedSummary.cancelled}</div>
              </div>
              <div className="rounded-2xl border border-border/70 p-4 text-sm">
                <div className="text-muted-foreground">{t("wakeups:aiCount")}</div>
                <div className="mt-2 text-xl font-semibold">{groupedSummary.ai}</div>
              </div>
            </CardContent>
          </Card>
        </div>

        <Card className="border-border/70 bg-card/90">
          <CardHeader>
            <CardTitle>{t("wakeups:listTitle")}</CardTitle>
            <CardDescription>{t("wakeups:listDescription")}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("wakeups:loading")}</div> : null}
            {!isLoading && !items.length ? <div className="rounded-lg border border-dashed border-border p-6 text-sm text-muted-foreground">{t("wakeups:empty")}</div> : null}
            {!isLoading
              ? items.map((item) => (
                  <div key={item.id} className="rounded-2xl border border-border/70 p-4">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <Badge variant={item.status === "queued" ? "default" : item.status === "cancelled" ? "secondary" : "outline"}>
                        {t(`wakeups:statusLabel.${item.status}`, { defaultValue: item.status })}
                      </Badge>
                      <Badge variant="outline">{item.target_type === "cocoon" ? t("wakeups:targetCocoon") : t("wakeups:targetChatGroup")}</Badge>
                      {item.is_ai_wakeup ? <Badge variant="outline">{t("wakeups:aiBadge")}</Badge> : null}
                    </div>
                    <div className="text-sm font-medium">{item.target_name || item.target_id}</div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {t("wakeups:runAt", { value: formatWorkspaceTime(item.run_at) })}
                    </div>
                    <div className="mt-3 text-sm">{item.reason || t("wakeups:noReason")}</div>
                    <div className="mt-3 flex flex-wrap gap-3 text-xs text-muted-foreground">
                      <span>{t("wakeups:scheduledBy", { value: item.scheduled_by || t("wakeups:unknownSource") })}</span>
                      <span>{t("wakeups:triggerKind", { value: item.trigger_kind || t("wakeups:noneValue") })}</span>
                      <span>{t("wakeups:createdAt", { value: formatWorkspaceTime(item.created_at) })}</span>
                    </div>
                    {item.cancelled_reason ? (
                      <div className="mt-2 text-xs text-muted-foreground">
                        {t("wakeups:cancelledReason", { value: item.cancelled_reason })}
                      </div>
                    ) : null}
                  </div>
                ))
              : null}
          </CardContent>
        </Card>
      </div>
    </PageFrame>
  );
}
