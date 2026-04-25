import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type PromptDialogOptions = {
  title: string;
  description?: string;
  label?: string;
  placeholder?: string;
  defaultValue?: string;
  confirmLabel?: string;
  cancelLabel?: string;
};

type PromptDialogState = PromptDialogOptions & {
  open: boolean;
};

const DEFAULT_STATE: PromptDialogState = {
  open: false,
  title: "",
  description: "",
  label: "",
  placeholder: "",
  defaultValue: "",
  confirmLabel: "Confirm",
  cancelLabel: "Cancel",
};

export function usePromptDialog() {
  const [state, setState] = useState<PromptDialogState>(DEFAULT_STATE);
  const [value, setValue] = useState("");
  const resolverRef = useRef<((value: string | null) => void) | null>(null);

  useEffect(
    () => () => {
      resolverRef.current?.(null);
      resolverRef.current = null;
    },
    [],
  );

  function resolve(nextValue: string | null) {
    resolverRef.current?.(nextValue);
    resolverRef.current = null;
    setState(DEFAULT_STATE);
    setValue("");
  }

  function prompt(options: PromptDialogOptions) {
    return new Promise<string | null>((resolvePromise) => {
      resolverRef.current = resolvePromise;
      const nextState = {
        ...DEFAULT_STATE,
        ...options,
        open: true,
      };
      setState(nextState);
      setValue(nextState.defaultValue || "");
    });
  }

  const dialog = (
    <Dialog
      open={state.open}
      onOpenChange={(open) => {
        if (!open && state.open) {
          resolve(null);
        }
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{state.title}</DialogTitle>
          {state.description ? <DialogDescription>{state.description}</DialogDescription> : null}
        </DialogHeader>
        <div className="grid gap-2 py-2">
          {state.label ? <Label htmlFor="prompt-dialog-input">{state.label}</Label> : null}
          <Input
            id="prompt-dialog-input"
            value={value}
            placeholder={state.placeholder}
            onChange={(event) => setValue(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && value.trim()) {
                resolve(value);
              }
            }}
          />
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => resolve(null)}>
            {state.cancelLabel}
          </Button>
          <Button disabled={!value.trim()} onClick={() => resolve(value)}>
            {state.confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );

  return { prompt, promptDialog: dialog };
}
