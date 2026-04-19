import type { ReactNode } from "react";

import { SidebarTrigger } from "@/components/ui/sidebar";
import { Separator } from "@/components/ui/separator";

export default function PageFrame({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
        <div className="flex items-start gap-3 px-4 py-3 md:items-center md:px-6">
          <div className="flex shrink-0 items-center gap-3">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="hidden data-[orientation=vertical]:h-5 sm:block" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="font-heading text-lg font-semibold leading-tight break-keep md:text-2xl">{title}</h1>
            {description ? (
              <p className="mt-1 hidden max-w-3xl text-sm leading-6 text-muted-foreground break-keep sm:block">
                {description}
              </p>
            ) : null}
          </div>
        </div>
      </header>
      <div className="flex-1 p-4 md:p-6">
        {actions ? <div className="mb-4 flex flex-wrap items-center gap-2 md:mb-6">{actions}</div> : null}
        {children}
      </div>
    </div>
  );
}
