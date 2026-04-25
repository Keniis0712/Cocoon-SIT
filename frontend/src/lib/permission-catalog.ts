const KNOWN_PERMISSIONS = [
  "users:read",
  "users:write",
  "roles:read",
  "roles:write",
  "cocoons:read",
  "cocoons:write",
  "characters:read",
  "characters:write",
  "tags:read",
  "tags:write",
  "providers:read",
  "providers:write",
  "prompt_templates:read",
  "prompt_templates:write",
  "plugins:read",
  "plugins:write",
  "plugins:run",
  "settings:read",
  "settings:write",
  "memory:read",
  "memory:write",
  "pulls:write",
  "merges:write",
  "checkpoints:read",
  "checkpoints:write",
  "audits:read",
  "insights:read",
  "artifacts:cleanup",
];

function titleCase(value: string) {
  return value
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function listKnownPermissions(extra: string[] = []) {
  return Array.from(new Set([...KNOWN_PERMISSIONS, ...extra])).sort((left, right) => {
    const leftIndex = KNOWN_PERMISSIONS.indexOf(left);
    const rightIndex = KNOWN_PERMISSIONS.indexOf(right);
    if (leftIndex === -1 && rightIndex === -1) return left.localeCompare(right);
    if (leftIndex === -1) return 1;
    if (rightIndex === -1) return -1;
    return leftIndex - rightIndex;
  });
}

export function groupPermissions(keys: string[]) {
  const groups = new Map<string, string[]>();
  for (const key of keys) {
    const [resource = "other"] = key.split(":");
    const bucket = groups.get(resource) || [];
    bucket.push(key);
    groups.set(resource, bucket);
  }

  return Array.from(groups.entries()).map(([resource, permissions]) => ({
    resource,
    label: titleCase(resource),
    permissions,
  }));
}

export function permissionLabel(key: string) {
  const [resource = key, action = ""] = key.split(":");
  return action ? `${titleCase(resource)} / ${titleCase(action)}` : titleCase(resource);
}
