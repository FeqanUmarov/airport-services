import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.modules.auth.repository import AuthRepository
from app.modules.auth.service import AuthenticatedUser
from app.modules.users.models import User
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserCreate, UserListResponse, UserResponse


class UserNotFoundError(ValueError):
    pass


class UserConflictError(ValueError):
    pass


class UserValidationError(ValueError):
    pass


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = UserRepository(session)
        self.auth_repository = AuthRepository(session)

    async def _roles(self, role_codes: list[str]):
        roles = await self.repository.get_active_roles(role_codes)
        found = {role.CODE for role in roles}
        missing = sorted(set(role_codes) - found)
        if missing:
            raise UserValidationError(f"Unknown or inactive roles: {', '.join(missing)}")
        return roles

    async def _response(self, user: User, status_name: str) -> UserResponse:
        role_map = await self.repository.get_roles_by_user_ids([user.USER_ID])
        return UserResponse(
            user_id=user.USER_ID,
            username=user.USERNAME,
            email=user.EMAIL,
            first_name=user.FIRST_NAME,
            last_name=user.LAST_NAME,
            status_id=user.STATUS_ID,
            status=status_name,
            roles=role_map.get(user.USER_ID, []),
            created_date=user.CREATED_DATE,
            last_edited_date=user.LAST_EDITED_DATE,
        )

    async def list_users(
        self,
        *,
        page: int,
        page_size: int,
        search: str | None,
        status_id: int | None,
    ) -> UserListResponse:
        rows, total = await self.repository.list_users(
            offset=(page - 1) * page_size,
            limit=page_size,
            search=search,
            status_id=status_id,
        )
        role_map = await self.repository.get_roles_by_user_ids(
            [user.USER_ID for user, _ in rows]
        )
        items = [
            UserResponse(
                user_id=user.USER_ID,
                username=user.USERNAME,
                email=user.EMAIL,
                first_name=user.FIRST_NAME,
                last_name=user.LAST_NAME,
                status_id=user.STATUS_ID,
                status=status_name,
                roles=role_map.get(user.USER_ID, []),
                created_date=user.CREATED_DATE,
                last_edited_date=user.LAST_EDITED_DATE,
            )
            for user, status_name in rows
        ]
        return UserListResponse(items=items, total=total, page=page, page_size=page_size)

    async def get_user(self, user_id: int) -> UserResponse:
        result = await self.repository.get_user(user_id)
        if result is None:
            raise UserNotFoundError("User does not exist")
        return await self._response(*result)

    async def create_user(self, payload: UserCreate) -> UserResponse:
        duplicate = await self.repository.find_duplicate(
            username=payload.username,
            email=str(payload.email),
        )
        if duplicate is not None:
            raise UserConflictError("Username or email already exists")

        active_status = await self.repository.get_active_status()
        if active_status is None:
            raise UserValidationError("Active status is not configured")
        roles = await self._roles(payload.role_codes)
        user = User(
            USERNAME=payload.username,
            EMAIL=str(payload.email).lower(),
            PASSWORD_HASH=await asyncio.to_thread(hash_password, payload.password),
            FIRST_NAME=payload.first_name,
            LAST_NAME=payload.last_name,
            STATUS_ID=active_status.STATUS_ID,
        )
        await self.repository.create_user(user, roles)
        await self.session.commit()
        return await self._response(user, active_status.ENG_NAME)

    async def update_user(self, user_id: int, changes: dict[str, object]) -> UserResponse:
        result = await self.repository.get_user(user_id)
        if result is None:
            raise UserNotFoundError("User does not exist")
        user, _ = result
        username = changes.get("username")
        email = changes.get("email")
        duplicate = await self.repository.find_duplicate(
            username=str(username) if username is not None else None,
            email=str(email) if email is not None else None,
            exclude_user_id=user_id,
        )
        if duplicate is not None:
            raise UserConflictError("Username or email already exists")

        fields = {
            "username": "USERNAME",
            "email": "EMAIL",
            "first_name": "FIRST_NAME",
            "last_name": "LAST_NAME",
        }
        for source, target in fields.items():
            if source in changes:
                value = str(changes[source])
                setattr(user, target, value.lower() if source == "email" else value)
        await self.session.commit()
        refreshed = await self.repository.get_user(user_id)
        if refreshed is None:  # pragma: no cover - guarded by the existing row
            raise UserNotFoundError("User does not exist")
        return await self._response(*refreshed)

    async def update_status(
        self,
        user_id: int,
        status_id: int,
        acting_admin: AuthenticatedUser,
    ) -> UserResponse:
        result = await self.repository.get_user(user_id)
        if result is None:
            raise UserNotFoundError("User does not exist")
        status = await self.repository.get_status(status_id)
        if status is None:
            raise UserValidationError("Status does not exist")
        if user_id == acting_admin.user.USER_ID and status.ENG_NAME.casefold() != "active":
            raise UserValidationError("You cannot deactivate your own account")

        user, _ = result
        user.STATUS_ID = status_id
        if status.ENG_NAME.casefold() != "active":
            await self.auth_repository.revoke_all_refresh_tokens(user_id, datetime.now(UTC))
        await self.session.commit()
        refreshed = await self.repository.get_user(user_id)
        if refreshed is None:  # pragma: no cover - guarded by the existing row
            raise UserNotFoundError("User does not exist")
        return await self._response(*refreshed)

    async def replace_roles(
        self,
        user_id: int,
        role_codes: list[str],
        acting_admin: AuthenticatedUser,
    ) -> UserResponse:
        result = await self.repository.get_user(user_id)
        if result is None:
            raise UserNotFoundError("User does not exist")
        if user_id == acting_admin.user.USER_ID and "ADMIN" not in role_codes:
            raise UserValidationError("You cannot remove your own ADMIN role")
        roles = await self._roles(role_codes)
        await self.repository.replace_roles(user_id, roles)
        await self.session.commit()
        return await self._response(*result)

    async def reset_password(self, user_id: int, new_password: str) -> None:
        result = await self.repository.get_user(user_id)
        if result is None:
            raise UserNotFoundError("User does not exist")
        user, _ = result
        user.PASSWORD_HASH = await asyncio.to_thread(hash_password, new_password)
        await self.auth_repository.revoke_all_refresh_tokens(user_id, datetime.now(UTC))
        await self.session.commit()

    async def revoke_tokens(self, user_id: int) -> None:
        if await self.repository.get_user(user_id) is None:
            raise UserNotFoundError("User does not exist")
        await self.auth_repository.revoke_all_refresh_tokens(user_id, datetime.now(UTC))
        await self.session.commit()
