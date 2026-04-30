import { beforeEach, describe, expect, it, vi } from "vitest";

import { formatWorkspaceTime, toFutureDateTimeLocalValue } from "@/features/workspace/utils";

describe("workspace utils", () => {
  beforeEach(() => {
    vi.useRealTimers();
  });

  it("formats missing timestamps as a dash", () => {
    expect(formatWorkspaceTime(null)).toBe("-");
    expect(formatWorkspaceTime(undefined)).toBe("-");
  });

  it("builds local datetime strings in the future", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-04-26T12:00:00Z"));

    const value = toFutureDateTimeLocalValue(15);
    expect(value).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    expect(value.endsWith(":15")).toBe(true);
  });
});
