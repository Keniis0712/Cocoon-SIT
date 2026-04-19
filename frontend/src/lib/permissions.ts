import type { SessionUser } from "@/api/user";

export function hasPermission(user: SessionUser | null | undefined, permission: string) {
  return Boolean(user?.permissions?.[permission]);
}

export function hasAnyPermission(user: SessionUser | null | undefined, permissions: string[]) {
  return permissions.some((permission) => hasPermission(user, permission));
}
