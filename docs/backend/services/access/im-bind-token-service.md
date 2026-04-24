# ImBindTokenService

Source: `backend/app/services/access/im_bind_token_service.py`

## Purpose

- Issues short-lived IM binding tokens for an existing Cocoon user.
- Enforces a single active token per user.
- Verifies a presented username/token pair before a plugin binds an external IM identity.

## Public Interface

- `issue_for_user(session, user)`
- `verify_user_token(session, username, token)`

## Notes

- Tokens are stored as hashes; the raw token is only returned at issue time.
- Verification prunes expired tokens before checking candidates.
- Expired or superseded rows are revoked in the same session so callers and tests see the updated ORM state immediately.
