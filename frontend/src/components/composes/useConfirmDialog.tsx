import { useEffect, useRef, useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

type ConfirmDialogOptions = {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "default" | "destructive";
};

type ConfirmDialogState = ConfirmDialogOptions & {
  open: boolean;
};

const DEFAULT_STATE: ConfirmDialogState = {
  open: false,
  title: "",
  description: "",
  confirmLabel: "Confirm",
  cancelLabel: "Cancel",
  variant: "default",
};

export function useConfirmDialog() {
  const [state, setState] = useState<ConfirmDialogState>(DEFAULT_STATE);
  const resolverRef = useRef<((value: boolean) => void) | null>(null);

  useEffect(
    () => () => {
      resolverRef.current?.(false);
      resolverRef.current = null;
    },
    [],
  );

  function resolve(value: boolean) {
    resolverRef.current?.(value);
    resolverRef.current = null;
    setState(DEFAULT_STATE);
  }

  function confirm(options: ConfirmDialogOptions) {
    return new Promise<boolean>((resolvePromise) => {
      resolverRef.current = resolvePromise;
      setState({
        open: true,
        confirmLabel: "Confirm",
        cancelLabel: "Cancel",
        variant: "default",
        description: "",
        ...options,
      });
    });
  }

  const dialog = (
    <AlertDialog
      open={state.open}
      onOpenChange={(open) => {
        if (!open && state.open) {
          resolve(false);
        }
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{state.title}</AlertDialogTitle>
          {state.description ? <AlertDialogDescription>{state.description}</AlertDialogDescription> : null}
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel onClick={() => resolve(false)}>{state.cancelLabel}</AlertDialogCancel>
          <AlertDialogAction variant={state.variant} onClick={() => resolve(true)}>
            {state.confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );

  return { confirm, confirmDialog: dialog };
}
