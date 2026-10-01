import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    TokenValidationError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    token_digest,
    verify_password,
)
from app.modules.auth.repository import AuthRepository
from app.modules.auth.schemas import CurrentUserResponse, TokenPair
from app.modules.users.models import User


class AuthenticationError(ValueError):
    pass


@dataclass(frozen=True)
class AuthenticatedUser:
    user: User
    roles: list[str]


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = AuthRepository(session)

    @staticmethod
    def _ensure_active(status_name: str) -> None:
        if status_name.casefold() != "active":
            raise AuthenticationError("Invalid credentials or inactive account")

    async def _issue_token_pair(self, user_id: int) -> TokenPair:
        access_token, _ = create_access_token(user_id)
        refresh_token, refresh_expires_at = create_refresh_token(user_id)
        await self.repository.add_refresh_token(
            user_id=user_id,
            digest=token_digest(refresh_token),
            expires_at=refresh_expires_at,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def login(self, login: str, password: str) -> TokenPair:
        result = await self.repository.get_user_by_login(login)
        if result is None:
            raise AuthenticationError("Invalid credentials or inactive account")

        user, status_name = result
        if not await asyncio.to_thread(verify_password, password, user.PASSWORD_HASH):
            raise AuthenticationError("Invalid credentials or inactive account")
        self._ensure_active(status_name)

        token_pair = await self._issue_token_pair(user.USER_ID)
        await self.session.commit()
        return token_pair

    async def logout_all(self, user_id: int) -> int:
        revoked_count = await self.repository.revoke_all_refresh_tokens(
            user_id,
            datetime.now(UTC),
        )
        await self.session.commit()
        return revoked_count

    async def change_password(
        self,
        authenticated: AuthenticatedUser,
        *,
        current_password: str,
        new_password: str,
    ) -> None:
        user = authenticated.user
        password_matches = await asyncio.to_thread(
            verify_password,
            current_password,
            user.PASSWORD_HASH,
        )
        if not password_matches:
            raise AuthenticationError("Current password is incorrect")
        if current_password == new_password:
            raise AuthenticationError("New password must be different")

        user.PASSWORD_HASH = await asyncio.to_thread(hash_password, new_password)
        await self.repository.revoke_all_refresh_tokens(
            user.USER_ID,
            datetime.now(UTC),
        )
        await self.session.commit()

    async def refresh(self, raw_refresh_token: str) -> TokenPair:
        try:
            payload = decode_token(raw_refresh_token, expected_type="refresh")
        except TokenValidationError as exc:
            raise AuthenticationError(str(exc)) from exc

        user_id = int(str(payload["sub"]))
        record = await self.repository.get_refresh_token_for_update(
            token_digest(raw_refresh_token)
        )
        now = datetime.now(UTC)
        if (
            record is None
            or record.USER_ID != user_id
            or record.REVOKED_AT is not None
            or record.EXPIRES_AT <= now
        ):
            raise AuthenticationError("Refresh token is revoked or expired")

        result = await self.repository.get_user_by_id(user_id)
        if result is None:
            raise AuthenticationError("User does not exist")
        _, status_name = result
        self._ensure_active(status_name)

        await self.repository.revoke_token(record, now)
        token_pair = await self._issue_token_pair(user_id)
        await self.session.commit()
        return token_pair

    async def logout(self, raw_refresh_token: str) -> None:
        try:
            payload = decode_token(raw_refresh_token, expected_type="refresh")
        except TokenValidationError as exc:
            raise AuthenticationError(str(exc)) from exc

        record = await self.repository.get_refresh_token_for_update(
            token_digest(raw_refresh_token)
        )
        if record is None or record.USER_ID != int(str(payload["sub"])):
            raise AuthenticationError("Refresh token does not exist")

        if record.REVOKED_AT is None:
            await self.repository.revoke_token(record, datetime.now(UTC))
        await self.session.commit()

    async def authenticate_access_token(self, raw_access_token: str) -> AuthenticatedUser:
        try:
            payload = decode_token(raw_access_token, expected_type="access")
        except TokenValidationError as exc:
            raise AuthenticationError(str(exc)) from exc

        user_id = int(str(payload["sub"]))
        result = await self.repository.get_user_by_id(user_id)
        if result is None:
            raise AuthenticationError("User does not exist")
        user, status_name = result
        self._ensure_active(status_name)
        roles = await self.repository.get_role_codes(user_id)
        return AuthenticatedUser(user=user, roles=roles)

    @staticmethod
    def to_current_user(authenticated: AuthenticatedUser) -> CurrentUserResponse:
        user = authenticated.user
        return CurrentUserResponse(
            user_id=user.USER_ID,
            username=user.USERNAME,
            email=user.EMAIL,
            first_name=user.FIRST_NAME,
            last_name=user.LAST_NAME,
            roles=authenticated.roles,
        )
