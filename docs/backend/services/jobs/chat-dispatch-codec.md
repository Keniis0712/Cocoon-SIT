# ChatDispatchCodec

Source: `backend/app/services/jobs/chat_dispatch_codec.py`

## Purpose

- Serializes and deserializes dispatch payloads for transport backends.
- Ensures Redis-backed queue payloads round-trip as structured JSON.

## Public Interface

- `encode_payload(payload)`
- `decode_payload(raw_payload)`

## Interactions

- Used by `RedisChatDispatchQueue`.
