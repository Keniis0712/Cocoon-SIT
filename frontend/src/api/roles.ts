import type { Schemas } from "@cocoon-sit/ts-sdk";

import { apiCall } from "./client";
import { rememberLegacyId } from "./id-map";
import type { PageResp, RoleRead } from "./types";

function makePage<T>(items: T[], page: number, pageSize: number): PageResp<T> {
  const total = items.length;
  const total_pages = Math.max(1, Math.ceil(total / pageSize));
  const start = Math.max(0, (page - 1) * pageSize);
  return {
    items: items.slice(start, start + pageSize),
    total,
    page,
    page_size: pageSize,
    total_pages,
  };
}

function toRoleCode(role: Schemas["RoleOut"]) {
  return role.name.trim().toLowerCase().replace(/\s+/g, "_");
}

function mapRole(role: Schemas["RoleOut"]): RoleRead {
  rememberLegacyId("role", role.id);
  return {
    code: toRoleCode(role),
    name: role.name,
    description: null,
    permissions_json: JSON.stringify(role.permissions_json || {}),
    is_system: ["admin", "operator", "user"].includes(toRoleCode(role)),
    created_at: "",
    updated_at: "",
  };
}

export function listRoles(page: number, page_size: number, q?: string): Promise<PageResp<RoleRead>> {
  return apiCall(async (client) => {
    const items = (await client.listRoles()).map(mapRole);
    const filtered = q ? items.filter((item) => item.name.includes(q) || item.code.includes(q)) : items;
    return makePage(filtered, page, page_size);
  });
}
