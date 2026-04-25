import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/button";

const ITEMS = [
  { to: "/invites", key: "codesTitle" },
  { to: "/invites/grants", key: "grantsTitle" },
  { to: "/invites/quotas", key: "summaryTitle" },
] as const;

export function InvitesSubnav() {
  const { t } = useTranslation("invites");
  const location = useLocation();

  return (
    <div className="flex flex-wrap gap-2">
      {ITEMS.map((item) => {
        const active = location.pathname === item.to;
        return (
          <Button key={item.to} asChild variant={active ? "default" : "outline"} size="sm">
            <Link to={item.to}>{t(item.key)}</Link>
          </Button>
        );
      })}
    </div>
  );
}
