import { Shield, ShieldPlus, UserPlus, UsersRound } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { ChatGroupMemberRead } from "@/api/types/chat-groups";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { formatWorkspaceTime } from "@/features/workspace/utils";

type ChatGroupSidebarProps = {
  characterName: string;
  modelLabel: string;
  dispatchState: string | null | undefined;
  relationScore: number | null | undefined;
  currentWakeupTaskId: string | null | undefined;
  debounceUntil: string | null | undefined;
  lastError: string | null | undefined;
  members: ChatGroupMemberRead[];
  canManage: boolean;
  ownerUserId: string | null | undefined;
  memberNameMap: Map<string, string>;
  onOpenAddMember: () => void;
  onToggleMemberRole: (member: ChatGroupMemberRead, nextRole: "member" | "admin") => void;
  onRemoveMember: (member: ChatGroupMemberRead) => void;
};

export function ChatGroupSidebar({
  characterName,
  modelLabel,
  dispatchState,
  relationScore,
  currentWakeupTaskId,
  debounceUntil,
  lastError,
  members,
  canManage,
  ownerUserId,
  memberNameMap,
  onOpenAddMember,
  onToggleMemberRole,
  onRemoveMember,
}: ChatGroupSidebarProps) {
  const { t } = useTranslation("chatGroups");

  return (
    <div className="space-y-4">
      <Card className="border-border/70 bg-card/90">
        <CardHeader>
          <CardTitle>{t("roomStateTitle")}</CardTitle>
          <CardDescription>{t("roomStateDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">{t("characterLabel", { value: characterName })}</Badge>
            <Badge variant="outline">{t("modelLabel", { value: modelLabel })}</Badge>
            <Badge variant="outline">{t("dispatchLabel", { value: dispatchState || "idle" })}</Badge>
            <Badge variant="outline">{t("relationLabel", { value: relationScore ?? "-" })}</Badge>
          </div>
          <div className="rounded-[22px] border border-border/70 bg-background/60 p-4 text-sm">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("wakeupPanelTitle")}</div>
            <div>{currentWakeupTaskId ? t("currentWakeupTask", { id: currentWakeupTaskId }) : t("noActiveWakeupTask")}</div>
            {debounceUntil ? (
              <div className="mt-2 text-xs text-muted-foreground">{t("debouncedUntil", { value: formatWorkspaceTime(debounceUntil) })}</div>
            ) : null}
            {lastError ? <div className="mt-2 text-sm text-destructive">{lastError}</div> : null}
          </div>
        </CardContent>
      </Card>

      <Card className="border-border/70 bg-card/90">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UsersRound className="size-4 text-orange-500" />
            {t("membersTitle")}
          </CardTitle>
          <CardDescription>{t("membersDescription")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {canManage ? (
            <Button className="w-full" variant="outline" onClick={onOpenAddMember}>
              <UserPlus className="mr-2 size-4" />
              {t("addMember")}
            </Button>
          ) : null}
          {members.map((member) => {
            const isOwner = ownerUserId === member.user_id;
            const memberName = memberNameMap.get(member.user_id) || member.user_id;
            return (
              <div key={member.id} className="rounded-[22px] border border-border/70 bg-background/60 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-medium">{memberName}</div>
                    <div className="mt-1 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      {isOwner ? <Badge>{t("owner")}</Badge> : <Badge variant="secondary">{member.member_role === "admin" ? t("adminRole") : t("memberRole")}</Badge>}
                      <span>{formatWorkspaceTime(member.created_at)}</span>
                    </div>
                  </div>
                  {canManage && !isOwner ? (
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onToggleMemberRole(member, member.member_role === "admin" ? "member" : "admin")}
                      >
                        {member.member_role === "admin" ? (
                          <>
                            <Shield className="mr-1 size-3" />
                            {t("makeMember")}
                          </>
                        ) : (
                          <>
                            <ShieldPlus className="mr-1 size-3" />
                            {t("makeAdmin")}
                          </>
                        )}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => onRemoveMember(member)}>
                        {t("removeMember")}
                      </Button>
                    </div>
                  ) : null}
                </div>
              </div>
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
