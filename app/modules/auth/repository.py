from datetime import datetime

from sqlalchemy import Select, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Status
from app.modules.auth.models import UserToken
from app.modules.users.models import Role, User, UserRole


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_login(self, login: str) -> tuple[User, str] | None:
        normalized = login.strip().lower()
        statement = (
            select(User, Status.ENG_NAME)
            .join(Status, Status.STATUS_ID == User.STATUS_ID)
            .where(
                (func.lower(User.USERNAME) == normalized)
                | (func.lower(User.EMAIL) == normalized)
            )
        )
        row = (await self.session.execute(statement)).one_or_none()
        return (row[0], row[1]) if row else None

    async def get_user_by_id(self, user_id: int) -> tuple[User, str] | None:
        statement = (
            select(User, Status.ENG_NAME)
            .join(Status, Status.STATUS_ID == User.STATUS_ID)
            .where(User.USER_ID == user_id)
        )
        row = (await self.session.execute(statement)).one_or_none()
        return (row[0], row[1]) if row else None

    async def get_role_codes(self, user_id: int) -> list[str]:
        statement = (
            select(Role.CODE)
            .join(UserRole, UserRole.ROLE_ID == Role.ROLE_ID)
            .join(Status, Status.STATUS_ID == Role.STATUS_ID)
            .where(UserRole.USER_ID == user_id, func.lower(Status.ENG_NAME) == "active")
            .order_by(Role.CODE)
        )
        return list((await self.session.scalars(statement)).all())

    async def add_refresh_token(
        self,
        *,
        user_id: int,
        digest: str,
        expires_at: datetime,
    ) -> UserToken:
        record = UserToken(
            USER_ID=user_id,
            REFRESH_TOKEN=digest,
            EXPIRES_AT=expires_at,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def get_refresh_token_for_update(self, digest: str) -> UserToken | None:
        statement: Select[tuple[UserToken]] = (
            select(UserToken)
            .where(UserToken.REFRESH_TOKEN == digest)
            .with_for_update()
        )
        return await self.session.scalar(statement)

    async def revoke_token(self, record: UserToken, revoked_at: datetime) -> None:
        record.REVOKED_AT = revoked_at
        await self.session.flush()

    async def revoke_all_refresh_tokens(
        self,
        user_id: int,
        revoked_at: datetime,
    ) -> int:
        result = await self.session.execute(
            update(UserToken)
            .where(
                UserToken.USER_ID == user_id,
                UserToken.REVOKED_AT.is_(None),
            )
            .values(REVOKED_AT=revoked_at)
        )
        return int(result.rowcount or 0)
