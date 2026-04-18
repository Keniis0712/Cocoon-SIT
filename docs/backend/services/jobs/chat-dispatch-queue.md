# ChatDispatchQueue

Source: `backend/app/services/jobs/chat_dispatch.py`

## Purpose

- Provides the compatibility export surface for chat dispatch queue abstractions and implementations.

## Public Interface

- `ChatDispatchQueue`
- `ChatDispatchEnvelope`
- `InMemoryChatDispatchQueue`
- `RedisChatDispatchQueue`
- `ChatDispatchCodec`

## Interactions

- Imported by workspace dispatch services, worker services, and the app container.
- Delegates concrete behavior to the split queue modules.
