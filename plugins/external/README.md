# External Plugins

English | [简体中文](README.zh-CN.md)

This directory contains external wakeup/event plugins.

## Purpose

- fetch data from third-party systems
- generate wakeup summaries or structured payloads
- run either on demand or on an admin-managed schedule

## Expected Manifest Features

An external plugin manifest usually includes:

- `plugin_type: "external"`
- `entry_module`
- `events[]`
- optional `settings_validation_function`
- plugin-level and user-level config schemas

Each event must declare a `mode`:

- `short_lived`: run once and return an envelope
- `daemon`: run continuously in an async task and push envelopes through the runtime queue

## Common Responsibilities

- validate plugin and user settings
- call external APIs or services
- convert remote data into concise summaries plus machine-readable payloads
- surface user-visible validation/runtime errors clearly

## Example

- [`qweather_daily_alert`](qweather_daily_alert/README.md)
