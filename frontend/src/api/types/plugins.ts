export interface UserPluginRead {
  id: string;
  name: string;
  display_name: string;
  plugin_type: string;
  status: string;
  is_globally_visible: boolean;
  is_visible: boolean;
  is_enabled: boolean;
  config_schema_json: Record<string, unknown>;
  default_config_json: Record<string, unknown>;
  user_config_schema_json: Record<string, unknown>;
  user_default_config_json: Record<string, unknown>;
  user_config_json: Record<string, unknown>;
  user_error_text: string | null;
  user_error_at: string | null;
}

export interface AdminPluginVersionRead {
  id: string;
  plugin_id: string;
  version: string;
  source_zip_path: string;
  extracted_path: string;
  manifest_path: string;
  install_status: string;
  error_text: string | null;
  metadata_json: Record<string, unknown>;
  created_at: string;
}

export interface AdminPluginEventRead {
  name: string;
  mode: string;
  function_name: string;
  title: string;
  description: string;
  config_schema_json: Record<string, unknown>;
  default_config_json: Record<string, unknown>;
  config_json: Record<string, unknown>;
  is_enabled: boolean;
  schedule_mode: "manual" | "interval" | "cron" | string;
  schedule_interval_seconds: number | null;
  schedule_cron: string | null;
}

export interface AdminPluginRunStateRead {
  id: string;
  plugin_id: string;
  current_version_id: string | null;
  process_type: string | null;
  pid: number | null;
  status: string;
  heartbeat_at: string | null;
  error_text: string | null;
  meta_json: Record<string, unknown>;
  updated_at: string;
}

export interface AdminPluginListItemRead {
  id: string;
  name: string;
  display_name: string;
  plugin_type: string;
  entry_module: string;
  service_function_name: string | null;
  status: string;
  install_source: string;
  data_dir: string;
  config_schema_json: Record<string, unknown>;
  default_config_json: Record<string, unknown>;
  config_json: Record<string, unknown>;
  user_config_schema_json: Record<string, unknown>;
  user_default_config_json: Record<string, unknown>;
  settings_validation_function_name: string | null;
  is_globally_visible: boolean;
  active_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AdminPluginDetailRead extends AdminPluginListItemRead {
  active_version: AdminPluginVersionRead | null;
  versions: AdminPluginVersionRead[];
  events: AdminPluginEventRead[];
  run_state: AdminPluginRunStateRead | null;
}

export interface AdminPluginSharedPackageRead {
  name: string;
  normalized_name: string;
  version: string;
  path: string;
  reference_count: number;
  size_bytes: number;
}

export interface PluginGroupVisibilityRead {
  id: string;
  plugin_id: string;
  group_id: string;
  is_visible: boolean;
  created_at: string;
  updated_at: string;
}

export interface PluginTargetBindingRead {
  id: string;
  plugin_id: string;
  scope_type: "user" | "chat_group" | string;
  scope_id: string;
  target_type: "cocoon" | "chat_group";
  target_id: string;
  target_name: string;
  created_at: string;
  updated_at: string;
}

export interface ChatGroupPluginConfigRead {
  plugin_id: string;
  chat_group_id: string;
  is_enabled: boolean;
  config_schema_json: Record<string, unknown>;
  default_config_json: Record<string, unknown>;
  config_json: Record<string, unknown>;
  error_text: string | null;
  error_at: string | null;
}
