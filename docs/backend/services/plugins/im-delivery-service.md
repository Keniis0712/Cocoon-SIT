# ImDeliveryService

Source: `backend/app/services/plugins/im_delivery_service.py`

## Purpose

- Delivers outbound IM messages from Cocoon runtime state into plugin-managed IM targets.
- Bridges workspace/runtime output and plugin routing records.

## Public Interface

- IM delivery helpers exposed by `ImDeliveryService`

## Notes

- This service is distinct from the plugin manager/runtime bootstrap layer.
- Pair it with `plugin-service.md` for lifecycle management and `plugin-runtime-manager.md` for process/runtime behavior.
