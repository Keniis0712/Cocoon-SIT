type Namespace =
  | "audit"
  | "character"
  | "checkpoint"
  | "cocoon"
  | "embedding-provider"
  | "group"
  | "group-member"
  | "invite"
  | "memory"
  | "merge"
  | "message"
  | "model"
  | "provider"
  | "role"
  | "tag"
  | "user";

type NamespaceState = {
  actualToLegacy: Record<string, number>;
  legacyToActual: Record<string, string>;
  next: number;
};

const STORAGE_KEY = "cocoon-legacy-id-map-v1";

const store: Record<Namespace, NamespaceState> = {
  audit: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  character: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  checkpoint: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  cocoon: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  "embedding-provider": { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  group: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  "group-member": { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  invite: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  memory: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  merge: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  message: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  model: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  provider: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  role: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  tag: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
  user: { actualToLegacy: {}, legacyToActual: {}, next: 1 },
};

let hydrated = false;

function hydrate() {
  if (hydrated || typeof window === "undefined") {
    hydrated = true;
    return;
  }

  hydrated = true;

  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;

    const parsed = JSON.parse(raw) as Partial<Record<Namespace, Partial<NamespaceState>>>;
    for (const namespace of Object.keys(store) as Namespace[]) {
      const next = parsed[namespace];
      if (!next) continue;
      store[namespace] = {
        actualToLegacy: next.actualToLegacy ?? {},
        legacyToActual: next.legacyToActual ?? {},
        next: Math.max(1, next.next ?? 1),
      };
    }
  } catch {
    // Ignore corrupted state and rebuild lazily.
  }
}

function persist() {
  if (typeof window === "undefined") {
    return;
  }

  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // Best effort only.
  }
}

export function rememberLegacyId(namespace: Namespace, actualId: string): number {
  hydrate();

  const scoped = store[namespace];
  const existing = scoped.actualToLegacy[actualId];
  if (existing) {
    return existing;
  }

  const next = scoped.next;
  scoped.next += 1;
  scoped.actualToLegacy[actualId] = next;
  scoped.legacyToActual[String(next)] = actualId;
  persist();
  return next;
}

export function rememberLegacyStringId(namespace: Namespace, actualId: string): string {
  return String(rememberLegacyId(namespace, actualId));
}

export function rememberOptionalLegacyStringId(
  namespace: Namespace,
  actualId: string | null | undefined,
): string | null {
  return actualId ? rememberLegacyStringId(namespace, actualId) : null;
}

export function resolveActualId(namespace: Namespace, legacyId: number | string): string {
  hydrate();

  if (typeof legacyId === "string" && /[a-z-]/i.test(legacyId)) {
    return legacyId;
  }

  return store[namespace].legacyToActual[String(legacyId)] ?? String(legacyId);
}
