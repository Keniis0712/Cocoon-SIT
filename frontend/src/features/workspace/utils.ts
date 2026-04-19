export function formatWorkspaceTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : "-";
}

export function toFutureDateTimeLocalValue(minutesFromNow = 10) {
  const now = new Date(Date.now() + minutesFromNow * 60 * 1000);
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

