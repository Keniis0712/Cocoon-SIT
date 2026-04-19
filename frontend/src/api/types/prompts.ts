export interface PromptTemplateRevisionRead {
  id: string;
  version: number;
  content: string;
  variables_json: string[];
  checksum: string;
  created_at: string;
}

export interface PromptTemplateRead {
  id: string;
  template_type: string;
  name: string;
  description: string;
  active_revision_id: string | null;
  created_at: string;
  updated_at: string;
  active_revision: PromptTemplateRevisionRead | null;
}

export interface PromptTemplatePayload {
  name: string;
  description: string;
  content: string;
}
