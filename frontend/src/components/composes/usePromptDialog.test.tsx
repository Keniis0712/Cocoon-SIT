import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useEffect } from "react";
import { describe, expect, it } from "vitest";

import { usePromptDialog } from "@/components/composes/usePromptDialog";

type PromptDialogApi = ReturnType<typeof usePromptDialog>;

function PromptDialogHarness({ onReady }: { onReady: (api: PromptDialogApi) => void }) {
  const api = usePromptDialog();

  useEffect(() => {
    onReady(api);
  }, [api, onReady]);

  return <>{api.promptDialog}</>;
}

describe("usePromptDialog", () => {
  it("returns the entered value when confirmed", async () => {
    let api: PromptDialogApi | null = null;
    render(<PromptDialogHarness onReady={(value) => (api = value)} />);

    await waitFor(() => expect(api).not.toBeNull());

    let pending: Promise<string | null> | undefined;
    await act(async () => {
      pending = api?.prompt({
        title: "Rename workspace",
        label: "Name",
        defaultValue: "Current",
        confirmLabel: "Save",
      });
    });

    const input = await screen.findByLabelText("Name");
    fireEvent.change(input, { target: { value: "Next name" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await expect(pending).resolves.toBe("Next name");
  });

  it("allows pressing enter to submit and returns null on cancel", async () => {
    let api: PromptDialogApi | null = null;
    render(<PromptDialogHarness onReady={(value) => (api = value)} />);

    await waitFor(() => expect(api).not.toBeNull());

    let submitPending: Promise<string | null> | undefined;
    await act(async () => {
      submitPending = api?.prompt({
        title: "Create tag",
        label: "Tag name",
      });
    });

    const input = await screen.findByLabelText("Tag name");
    fireEvent.change(input, { target: { value: "urgent" } });
    fireEvent.keyDown(input, { key: "Enter", code: "Enter" });

    await expect(submitPending).resolves.toBe("urgent");

    let cancelPending: Promise<string | null> | undefined;
    await act(async () => {
      cancelPending = api?.prompt({
        title: "Create tag",
        cancelLabel: "Dismiss",
      });
    });

    fireEvent.click(await screen.findByRole("button", { name: "Dismiss" }));

    await expect(cancelPending).resolves.toBeNull();
  });
});
