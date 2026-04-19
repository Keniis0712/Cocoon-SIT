export interface AvailableModelRead {
  id: number;
  provider_id: number;
  model_name: string;
  created_at: string;
  updated_at: string;
}

export interface ModelProviderRead {
  id: number;
  name: string;
  base_url: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
  available_models: AvailableModelRead[];
}

export interface ModelProviderPayload {
  name: string;
  base_url: string;
  api_key: string;
  is_enabled: boolean;
}

export interface StructuredModelTestRead {
  name: string;
  raw_text: string;
  parsed_result: Record<string, unknown>;
}

export interface ModelProviderTestResponse {
  provider_id: number;
  selected_model_id: number;
  model_name: string;
  reply: string;
  structured_tests: StructuredModelTestRead[];
}

export interface AllowedModelRead {
  id: number;
  provider_id: number;
  provider_name: string;
  model_name: string;
}

export interface PublicFeaturesRead {
  allow_registration: boolean;
  max_chat_turns: number;
  allowed_models: AllowedModelRead[];
  rollback_retention_days: number;
  rollback_cleanup_interval_hours: number;
}

export interface EmbeddingProviderRead {
  id: number;
  name: string;
  kind: "local_cpu" | "openai_compatible" | string;
  base_url: string | null;
  model_name: string | null;
  local_model_name: string | null;
  device: string;
  is_enabled: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface EmbeddingProviderPayload {
  name: string;
  kind: "local_cpu" | "openai_compatible" | string;
  base_url?: string | null;
  api_key?: string | null;
  model_name?: string | null;
  local_model_name?: string | null;
  device?: string;
  is_enabled?: boolean;
  is_default?: boolean;
}
