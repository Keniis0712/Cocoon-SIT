import { useEffect, useMemo, useState } from "react";
import { Check, ChevronsUpDown, Search } from "lucide-react";
import { useTranslation } from "react-i18next";

import type { PopupSelectOption } from "@/components/composes/PopupSelect";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";

type PopupMultiSelectProps = {
  title: string;
  description?: string;
  placeholder: string;
  searchPlaceholder?: string;
  emptyText?: string;
  value: string[];
  onValueChange: (value: string[]) => void;
  options: PopupSelectOption[];
  disabled?: boolean;
  pageSize?: number;
  triggerClassName?: string;
};

export function PopupMultiSelect({
  title,
  description,
  placeholder,
  searchPlaceholder,
  emptyText,
  value,
  onValueChange,
  options,
  disabled = false,
  pageSize = 8,
  triggerClassName,
}: PopupMultiSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const resolvedSearchPlaceholder = searchPlaceholder || t("common.search");
  const resolvedEmptyText = emptyText || t("common.notSet");
  const selectedSet = useMemo(() => new Set(value), [value]);
  const filteredOptions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) {
      return options;
    }
    return options.filter((option) => {
      const haystack = [option.label, option.description || "", ...(option.keywords || [])].join(" ").toLowerCase();
      return haystack.includes(normalized);
    });
  }, [options, query]);
  const [page, setPage] = useState(1);
  const totalPages = Math.max(1, Math.ceil(filteredOptions.length / pageSize));
  const pageOptions = useMemo(() => {
    const start = (page - 1) * pageSize;
    return filteredOptions.slice(start, start + pageSize);
  }, [filteredOptions, page, pageSize]);
  const selectedLabels = useMemo(
    () => options.filter((option) => selectedSet.has(option.value)).map((option) => option.label),
    [options, selectedSet],
  );

  useEffect(() => {
    setPage(1);
  }, [query, open]);

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  function toggleValue(optionValue: string) {
    if (selectedSet.has(optionValue)) {
      onValueChange(value.filter((item) => item !== optionValue));
      return;
    }
    onValueChange([...value, optionValue]);
  }

  return (
    <>
      <Button
        type="button"
        variant="outline"
        className={triggerClassName || "w-full justify-between"}
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        <span className="truncate text-left">
          {selectedLabels.length ? selectedLabels.join(", ") : placeholder}
        </span>
        <ChevronsUpDown className="ml-2 size-4 shrink-0 text-muted-foreground" />
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            {description ? <DialogDescription>{description}</DialogDescription> : null}
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="relative">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
              <Input className="pl-9" value={query} placeholder={resolvedSearchPlaceholder} onChange={(event) => setQuery(event.target.value)} />
            </div>
            <div className="max-h-[52vh] overflow-y-auto rounded-2xl border border-border/70 bg-background/60 p-2">
              {pageOptions.length ? (
                <div className="space-y-2">
                  {pageOptions.map((option) => {
                    const active = selectedSet.has(option.value);
                    return (
                      <button
                        key={option.value}
                        type="button"
                        onClick={() => toggleValue(option.value)}
                        className={`flex w-full items-start justify-between gap-3 rounded-2xl border px-4 py-3 text-left transition ${
                          active ? "border-primary bg-primary/8" : "border-border/70 hover:border-primary/40 hover:bg-accent/40"
                        }`}
                      >
                        <div className="min-w-0">
                          <div className="truncate font-medium">{option.label}</div>
                          {option.description ? (
                            <div className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">{option.description}</div>
                          ) : null}
                        </div>
                        {active ? <Check className="mt-0.5 size-4 shrink-0 text-primary" /> : null}
                      </button>
                    );
                  })}
                </div>
              ) : (
                <div className="rounded-2xl border border-dashed border-border px-4 py-8 text-center text-sm text-muted-foreground">
                  {resolvedEmptyText}
                </div>
              )}
            </div>
          </div>
          <DialogFooter className="items-center justify-between sm:justify-between">
            <div className="text-sm text-muted-foreground">
              {filteredOptions.length ? `${page} / ${totalPages}` : "0 / 0"}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => onValueChange([])}>
                {t("common.clear")}
              </Button>
              <Button variant="outline" disabled={page <= 1} onClick={() => setPage((current) => Math.max(1, current - 1))}>
                {t("common.previousPage")}
              </Button>
              <Button
                variant="outline"
                disabled={page >= totalPages || filteredOptions.length === 0}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              >
                {t("common.nextPage")}
              </Button>
            </div>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
