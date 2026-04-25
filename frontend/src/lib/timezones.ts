import type { PopupSelectOption } from "@/components/composes/PopupSelect";

const FALLBACK_TIMEZONES = [
  "UTC",
  "America/Los_Angeles",
  "America/Denver",
  "America/Chicago",
  "America/New_York",
  "America/Sao_Paulo",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Paris",
  "Europe/Moscow",
  "Asia/Dubai",
  "Asia/Kolkata",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Shanghai",
  "Asia/Hong_Kong",
  "Asia/Seoul",
  "Asia/Tokyo",
  "Australia/Sydney",
  "Pacific/Auckland",
];

const PRIORITY_TIMEZONES = [
  "UTC",
  "America/Los_Angeles",
  "America/New_York",
  "Europe/London",
  "Europe/Berlin",
  "Asia/Shanghai",
  "Asia/Singapore",
  "Asia/Tokyo",
];

type IntlWithSupportedValuesOf = typeof Intl & {
  supportedValuesOf?: (key: string) => string[];
};

function unique(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function isValidTimezone(value: string) {
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: value });
    return true;
  } catch {
    return false;
  }
}

function supportedTimezones() {
  const intlWithSupportedValuesOf = Intl as IntlWithSupportedValuesOf;
  const supported = intlWithSupportedValuesOf.supportedValuesOf?.("timeZone") || [];
  if (!supported.length) {
    return FALLBACK_TIMEZONES;
  }
  return unique(["UTC", ...supported]);
}

function offsetMinutesForTimezone(timeZone: string) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    timeZoneName: "shortOffset",
  }).formatToParts(new Date());
  const offsetPart = parts.find((part) => part.type === "timeZoneName")?.value || "GMT";
  const match = offsetPart.match(/^GMT(?:(?<sign>[+-])(?<hours>\d{1,2})(?::(?<minutes>\d{2}))?)?$/);
  if (!match?.groups?.sign || !match.groups.hours) {
    return 0;
  }
  const sign = match.groups.sign === "-" ? -1 : 1;
  const hours = Number(match.groups.hours || "0");
  const minutes = Number(match.groups.minutes || "0");
  return sign * (hours * 60 + minutes);
}

function formatOffsetLabel(offsetMinutes: number) {
  if (offsetMinutes === 0) {
    return "UTC";
  }
  const sign = offsetMinutes < 0 ? "-" : "+";
  const absoluteMinutes = Math.abs(offsetMinutes);
  const hours = String(Math.floor(absoluteMinutes / 60)).padStart(2, "0");
  const minutes = String(absoluteMinutes % 60).padStart(2, "0");
  return `UTC${sign}${hours}:${minutes}`;
}

function humanizeTimezone(timeZone: string) {
  if (timeZone === "UTC" || timeZone === "Etc/UTC") {
    return "UTC";
  }
  const parts = timeZone.split("/").map((part) => part.replace(/_/g, " "));
  return parts[parts.length - 1] || timeZone;
}

function timezoneKeywords(timeZone: string, offsetLabel: string) {
  const slashParts = timeZone.split("/");
  const spacedParts = slashParts.map((part) => part.replace(/_/g, " "));
  const offsetKeyword = offsetLabel.replace(":", "");
  return unique([
    timeZone,
    ...slashParts,
    ...spacedParts,
    spacedParts.join(" "),
    offsetLabel,
    offsetKeyword,
  ]);
}

function timezoneOption(timeZone: string): PopupSelectOption {
  const offsetLabel = formatOffsetLabel(offsetMinutesForTimezone(timeZone));
  return {
    value: timeZone,
    label: `${offsetLabel} - ${humanizeTimezone(timeZone)}`,
    description: timeZone,
    keywords: timezoneKeywords(timeZone, offsetLabel),
  };
}

function compareTimezones(left: string, right: string) {
  const offsetDelta = offsetMinutesForTimezone(left) - offsetMinutesForTimezone(right);
  if (offsetDelta !== 0) {
    return offsetDelta;
  }
  return left.localeCompare(right);
}

export function resolveBrowserTimezone(): string {
  if (typeof Intl === "undefined") {
    return "UTC";
  }
  const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  return isValidTimezone(timezone) ? timezone : "UTC";
}

export function buildTimezoneOptions({
  browserTimezone,
  currentTimezone,
}: {
  browserTimezone?: string;
  currentTimezone?: string;
}) {
  const allTimezones = supportedTimezones().filter(isValidTimezone);
  const preferred = unique([
    browserTimezone || "",
    currentTimezone || "",
    ...PRIORITY_TIMEZONES,
  ]).filter(isValidTimezone);
  const remainder = allTimezones
    .filter((timeZone) => !preferred.includes(timeZone))
    .sort(compareTimezones);
  return [...preferred, ...remainder].map(timezoneOption);
}
