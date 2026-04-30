import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { copyTextToClipboard } from "@/lib/clipboard";

describe("copyTextToClipboard", () => {
  const originalClipboard = navigator.clipboard;
  const originalExecCommand = document.execCommand;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    Object.defineProperty(navigator, "clipboard", {
      value: originalClipboard,
      configurable: true,
    });
    document.execCommand = originalExecCommand;
    document.body.innerHTML = "";
  });

  it("uses the async clipboard api when available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    await copyTextToClipboard("hello");

    expect(writeText).toHaveBeenCalledWith("hello");
  });

  it("falls back to execCommand and cleans up the temporary textarea", async () => {
    Object.defineProperty(navigator, "clipboard", {
      value: undefined,
      configurable: true,
    });
    document.execCommand = vi.fn().mockReturnValue(true);

    await copyTextToClipboard("fallback");

    expect(document.execCommand).toHaveBeenCalledWith("copy");
    expect(document.querySelector("textarea")).toBeNull();
  });
});
