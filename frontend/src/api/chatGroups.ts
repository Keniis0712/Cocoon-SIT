import { unsupportedFeature } from "./client";
import type { ChatGroupPayload, ChatGroupRead, PageResp } from "./types";

function makePage<T>(items: T[], page: number, pageSize: number): PageResp<T> {
  return {
    items,
    total: items.length,
    page,
    page_size: pageSize,
    total_pages: 1,
  };
}

export function listChatGroups(page = 1, page_size = 100) {
  return Promise.resolve(makePage<ChatGroupRead>([], page, page_size));
}

export function createChatGroup(_payload: ChatGroupPayload) {
  return unsupportedFeature("Chat group management is not supported by the current backend");
}

export function updateChatGroup(_groupId: number, _payload: Partial<ChatGroupPayload>) {
  return unsupportedFeature("Chat group management is not supported by the current backend");
}

export function deleteChatGroup(_groupId: number) {
  return unsupportedFeature("Chat group management is not supported by the current backend");
}
