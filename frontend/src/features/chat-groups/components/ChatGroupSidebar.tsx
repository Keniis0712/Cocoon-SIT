import { Plus, Shield, ShieldPlus, UserPlus, UsersRound } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { TagRead } from "@/api/types/catalog";
import type { ChatGroupMemberRead } from "@/api/types/chat-groups";
import type { WakeupTaskRead } from "@/api/types/wakeups";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { formatWorkspaceTime } from "@/features/workspace/utils";

const DEFAULT_RELATION_SCORE = 50;

type ChatGroupSidebarProps = {
  characterName: string;
  modelLabel: string;
  roomTags: TagRead[];
  sessionActiveTags: string[];
  availableAddableTags: TagRead[];
  addTagValue: string;
  isUpdatingTags: boolean;
  dispatchState: string | null | undefined;
  relationScore: number | null | undefined;
  currentAiWakeup: WakeupTaskRead | null;
  debounceUntil: string | null | undefined;
  lastError: string | null | undefined;
  members: ChatGroupMemberRead[];
  canManage: boolean;
  ownerUserId: string | null | undefined;
  memberNameMap: Map<string, string>;
  onAddTag: (value: string) => void;
  onRemoveTag: (tagId: number) => void;
  onOpenAddMember: () => void;
  onToggleMemberRole: (member: ChatGroupMemberRead, nextRole: "member" | "admin") => void;
  onRemoveMember: (member: ChatGroupMemberRead) => void;
};

export function ChatGroupSidebar({
  characterName,
  modelLabel,
  roomTags,
  sessionActiveTags,
  availableAddableTags,
  addTagValue,
  isUpdatingTags,
  dispatchState,
  relationScore,
  currentAiWakeup,
  debounceUntil,
  lastError,
  members,
  canManage,
  ownerUserId,
  memberNameMap,
  onAddTag,
  onRemoveTag,
  onOpenAddMember,
  onToggleMemberRole,
  onRemoveMember,
}: ChatGroupSidebarProps) {
  const { t } = useTranslation(["chatGroups", "wakeups"]);
  const tagLabelByKey = new Map<string, string>();
  for (const tag of roomTags.filter((item) => !item.is_system)) {
    tagLabelByKey.set(tag.actual_id, tag.name);
    tagLabelByKey.set(tag.tag_id, tag.name);
    tagLabelByKey.set(String(tag.id), tag.name);
  }
  const activeTags = sessionActiveTags.length
    ? sessionActiveTags
        .filter((tag) => tagLabelByKey.has(tag))
        .map((tag) => ({ key: tag, label: tagLabelByKey.get(tag) || tag }))
    : roomTags.filter((item) => !item.is_system).map((item) => ({ key: item.actual_id, label: item.name }));
  const visibleRoomTags = roomTags.filter((item) => !item.is_system);
  const displayTags = visibleRoomTags.length
    ? visibleRoomTags.map((item) => ({ key: item.actual_id, label: item.name, id: item.id }))
    : activeTags.map((item) => ({ ...item, id: null }));

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
            <Badge variant="outline">{t("relationLabel", { value: relationScore ?? DEFAULT_RELATION_SCORE })}</Badge>
          </div>
          <div className="rounded-[22px] border border-border/70 bg-background/60 p-4 text-sm">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">Tags</div>
            <div className="flex flex-wrap gap-2">
              {displayTags.length ? displayTags.map((tag) => (
                canManage && tag.id !== null ? (
                  <button
                    key={tag.key}
                    type="button"
                    className="inline-flex items-center rounded-full"
                    disabled={isUpdatingTags}
                    onClick={() => onRemoveTag(tag.id)}
                  >
                    <Badge variant="secondary">{tag.label} x</Badge>
                  </button>
                ) : (
                  <Badge key={tag.key} variant="secondary">
                    {tag.label}
                  </Badge>
                )
              )) : <span className="text-muted-foreground">No visible tags</span>}
            </div>
            {canManage ? (
              <div className="mt-3">
                <Select value={addTagValue} onValueChange={onAddTag} disabled={isUpdatingTags || !availableAddableTags.length}>
                  <SelectTrigger>
                    <SelectValue placeholder="Add tag" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__add">
                      <span className="inline-flex items-center gap-2">
                        <Plus className="size-4" />
                        Add tag
                      </span>
                    </SelectItem>
                    {availableAddableTags.map((tag) => (
                      <SelectItem key={tag.actual_id} value={String(tag.id)}>
                        {tag.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            ) : null}
          </div>
          <div className="rounded-[22px] border border-border/70 bg-background/60 p-4 text-sm">
            <div className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{t("wakeupPanelTitle")}</div>
            {currentAiWakeup ? (
              <div className="space-y-1">
                <div>{t("wakeups:aiWakeupAt", { value: formatWorkspaceTime(currentAiWakeup.run_at) })}</div>
                <div className="text-xs text-muted-foreground">
                  {t("wakeups:aiWakeupReason", { value: currentAiWakeup.reason || t("wakeups:unknownWakeupReason") })}
                </div>
              </div>
            ) : (
              <div>{t("noActiveWakeupTask")}</div>
            )}
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
