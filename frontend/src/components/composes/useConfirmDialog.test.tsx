import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, it } from "vitest";

import { useConfirmDialog } from "@/components/composes/useConfirmDialog";

type ConfirmDialogApi = ReturnType<typeof useConfirmDialog>;

function ConfirmDialogHarness({ onReady }: { onReady: (api: ConfirmDialogApi) => void }) {
  const api = useConfirmDialog();

  useEffect(() => {
    onReady(api);
  }, [api, onReady]);

  return <>{api.confirmDialog}</>;
}

describe("useConfirmDialog", () => {
  it("resolves true when the confirm action is chosen", async () => {
    let api: ConfirmDialogApi | null = null;
    render(<ConfirmDialogHarness onReady={(value) => (api = value)} />);

    await waitFor(() => expect(api).not.toBeNull());

    let pending: Promise<boolean> | undefined;
    await act(async () => {
      pending = api?.confirm({
        title: "Delete draft",
        description: "This cannot be undone.",
        confirmLabel: "Delete",
      });
    });

    expect(await screen.findByText("Delete draft")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await expect(pending).resolves.toBe(true);
  });

  it("resolves false when the cancel action is chosen", async () => {
    let api: ConfirmDialogApi | null = null;
    render(<ConfirmDialogHarness onReady={(value) => (api = value)} />);

    await waitFor(() => expect(api).not.toBeNull());

    let pending: Promise<boolean> | undefined;
    await act(async () => {
      pending = api?.confirm({
        title: "Archive room",
        cancelLabel: "Keep it",
      });
    });

    fireEvent.click(await screen.findByRole("button", { name: "Keep it" }));

    await expect(pending).resolves.toBe(false);
  });
});
