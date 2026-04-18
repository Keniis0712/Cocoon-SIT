# AuditLinkService

Source: `backend/app/services/audit/audit_link_service.py`

## Purpose

- Records graph-style relationships between audit steps and artifacts.

## Public Interface

- `record_link(session, run, relation, ...)`

## Interactions

- Used by the `AuditService` facade.
- Typically links generator outputs, prompt snapshots, and step provenance.
