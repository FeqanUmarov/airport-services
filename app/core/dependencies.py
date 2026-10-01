from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.modules.auth.service import AuthenticatedUser, AuthenticationError, AuthService


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    session: DatabaseSession,
) -> AuthenticatedUser:
    try:
        return await AuthService(session).authenticate_access_token(token)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_roles(*required_roles: str):
    required = set(required_roles)

    async def dependency(current: CurrentUser) -> AuthenticatedUser:
        if not required.intersection(current.roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current

    return dependency


AdminUser = Annotated[AuthenticatedUser, Depends(require_roles("ADMIN"))]
EditorUser = Annotated[
    AuthenticatedUser,
    Depends(require_roles("ADMIN", "EDITOR")),
]
