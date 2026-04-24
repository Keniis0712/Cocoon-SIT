# IM Plugins

English | [简体中文](README.zh-CN.md)

This directory contains IM bridge plugins.

## Purpose

- Connect external messaging platforms to Cocoon workspaces
- Translate inbound platform messages into Cocoon targets
- Deliver Cocoon replies back to the external platform

## Expected Manifest Features

An IM plugin manifest usually includes:

- `plugin_type: "im"`
- `entry_module`
- `service_function`
- optional `settings_validation_function`
- plugin-level `config_schema` and `default_config`

Unlike external plugins, IM plugins do not declare `events[]`. They run as dedicated long-lived bridge processes.

## Common Responsibilities

- maintain the platform connection
- map platform conversations to Cocoon targets
- persist local bridge state under the plugin data directory
- expose user-facing bind or attach commands when the platform supports them
- deliver outbound replies with retry/error signaling through the IM SDK

## Example

- [`nonebot_onebot_v11_bridge`](nonebot_onebot_v11_bridge/README.md)
