import { apiCall } from "./client";
import type { PromptTemplatePayload, PromptTemplateRead, PromptTemplateRevisionRead } from "./types/prompts";

function mapRevision(
  item:
    | {
        id: string;
        version: number;
        content: string;
        variables_json: string[];
        checksum: string;
        created_at: string;
      }
    | null
    | undefined,
): PromptTemplateRevisionRead | null {
  if (!item) {
    return null;
  }
  return {
    id: item.id,
    version: item.version,
    content: item.content,
    variables_json: item.variables_json,
    checksum: item.checksum,
    created_at: item.created_at,
  };
}

function mapTemplate(item: {
  id: string;
  template_type: string;
  name: string;
  description: string;
  active_revision_id: string | null;
  created_at: string;
  updated_at: string;
  active_revision?: {
    id: string;
    version: number;
    content: string;
    variables_json: string[];
    checksum: string;
    created_at: string;
  } | null;
}): PromptTemplateRead {
  return {
    id: item.id,
    template_type: item.template_type,
    name: item.name,
    description: item.description,
    active_revision_id: item.active_revision_id,
    created_at: item.created_at,
    updated_at: item.updated_at,
    active_revision: mapRevision(item.active_revision),
  };
}

export function listPromptTemplates(): Promise<PromptTemplateRead[]> {
  return apiCall(async (client) => {
    const items = await client.listPromptTemplates();
    return items.map(mapTemplate);
  });
}

export function savePromptTemplate(templateType: string, payload: PromptTemplatePayload): Promise<PromptTemplateRead> {
  return apiCall(async (client) => {
    await client.updatePromptTemplate(templateType, payload);
    const items = await client.listPromptTemplates();
    const template = items.find((item) => item.template_type === templateType);
    if (!template) {
      throw new Error(`Prompt template "${templateType}" was not found after save`);
    }
    return mapTemplate(template);
  });
}

export function resetPromptTemplate(templateType: string): Promise<PromptTemplateRead> {
  return apiCall(async (client) => {
    await client.resetPromptTemplate(templateType);
    const items = await client.listPromptTemplates();
    const template = items.find((item) => item.template_type === templateType);
    if (!template) {
      throw new Error(`Prompt template "${templateType}" was not found after reset`);
    }
    return mapTemplate(template);
  });
}
