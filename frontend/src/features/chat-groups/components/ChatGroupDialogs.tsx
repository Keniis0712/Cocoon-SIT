import type { AdminUserRead } from "@/api/types/access";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

type ChatGroupMemberDialogProps = {
  open: boolean;
  userId: string;
  role: "member" | "admin";
  userChoices: AdminUserRead[];
  onOpenChange: (open: boolean) => void;
  onUserIdChange: (value: string) => void;
  onRoleChange: (value: "member" | "admin") => void;
  onSubmit: () => void;
  onCancel: () => void;
};

export function ChatGroupMemberDialog({
  open,
  userId,
  role,
  userChoices,
  onOpenChange,
  onUserIdChange,
  onRoleChange,
  onSubmit,
  onCancel,
}: ChatGroupMemberDialogProps) {
  const { t } = useTranslation(["chatGroups", "common"]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>{t("chatGroups:addMemberTitle")}</DialogTitle>
          <DialogDescription>
            {t("chatGroups:addMemberDescription")}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-2">
          {userChoices.length > 0 ? (
            <div className="grid gap-2">
              <Label>{t("chatGroups:userLabel")}</Label>
              <Select value={userId} onValueChange={onUserIdChange}>
                <SelectTrigger>
                  <SelectValue placeholder={t("chatGroups:selectUser")} />
                </SelectTrigger>
                <SelectContent>
                  {userChoices.map((user) => (
                    <SelectItem key={user.uid} value={user.uid}>
                      {user.username}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div className="grid gap-2">
              <Label>{t("chatGroups:userIdLabel")}</Label>
              <Input value={userId} onChange={(event) => onUserIdChange(event.target.value)} placeholder={t("chatGroups:userIdPlaceholder")} />
            </div>
          )}
          <div className="grid gap-2">
            <Label>{t("chatGroups:roleLabel")}</Label>
            <Select value={role} onValueChange={onRoleChange}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="member">{t("chatGroups:memberRole")}</SelectItem>
                <SelectItem value="admin">{t("chatGroups:adminRole")}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onCancel}>
            {t("common:cancel")}
          </Button>
          <Button disabled={!userId.trim()} onClick={onSubmit}>
            {t("chatGroups:addMember")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
