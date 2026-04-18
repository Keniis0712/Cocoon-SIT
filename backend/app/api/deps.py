from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.container import AppContainer
from app.core.config import Settings
from app.models import User
from app.services.security.rbac import require_permission as enforce_permission
from app.services.security.token_authentication_service import TokenAuthenticationService


bearer_scheme = HTTPBearer(auto_error=False)


def get_container(request: Request) -> AppContainer:
    return request.app.state.container


def get_settings(container: AppContainer = Depends(get_container)) -> Settings:
    return container.settings


def get_token_authentication_service(
    container: AppContainer = Depends(get_container),
) -> TokenAuthenticationService:
    return container.token_authentication_service


def get_db(container: AppContainer = Depends(get_container)) -> Generator[Session, None, None]:
    session = container.session_factory()
    session.info["container"] = container
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    token_auth_service: TokenAuthenticationService = Depends(get_token_authentication_service),
) -> User:
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    return token_auth_service.resolve_active_user(db, credentials.credentials)


def require_permission(permission: str):
    def dependency(
        db: Session = Depends(get_db),
        user: User = Depends(get_current_user),
    ) -> User:
        enforce_permission(db, user, permission)
        return user

    return dependency
