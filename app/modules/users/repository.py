from collections.abc import Sequence

from sqlalchemy import delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Status
from app.modules.users.models import Role, User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_users(self, *, offset: int, limit: int, search: str | None, status_id: int | None) -> tuple[list[tuple[User, str]], int]:
        conditions = []
        if search:
            pattern = f"%{search.strip().lower()}%"
            conditions.append(or_(func.lower(User.USERNAME).like(pattern), func.lower(User.EMAIL).like(pattern), func.lower(User.FIRST_NAME).like(pattern), func.lower(User.LAST_NAME).like(pattern)))
        if status_id is not None:
            conditions.append(User.STATUS_ID == status_id)

        total = int((await self.session.scalar(select(func.count(User.USER_ID)).where(*conditions))) or 0)
        statement = select(User, Status.ENG_NAME).join(Status, Status.STATUS_ID == User.STATUS_ID).where(*conditions).order_by(User.USER_ID).offset(offset).limit(limit)
        rows = (await self.session.execute(statement)).all()
        return [(row[0], row[1]) for row in rows], total

    async def get_user(self, user_id: int) -> tuple[User, str] | None:
        statement = select(User, Status.ENG_NAME).join(Status, Status.STATUS_ID == User.STATUS_ID).where(User.USER_ID == user_id)
        row = (await self.session.execute(statement)).one_or_none()
        return (row[0], row[1]) if row else None

    async def find_duplicate(self, *, username: str | None, email: str | None, exclude_user_id: int | None = None) -> User | None:
        conditions = []
        if username is not None:
            conditions.append(func.lower(User.USERNAME) == username.lower())
        if email is not None:
            conditions.append(func.lower(User.EMAIL) == email.lower())
        if not conditions:
            return None
        statement = select(User).where(or_(*conditions))
        if exclude_user_id is not None:
            statement = statement.where(User.USER_ID != exclude_user_id)
        return await self.session.scalar(statement)

    async def get_status(self, status_id: int) -> Status | None:
        return await self.session.get(Status, status_id)

    async def get_active_status(self) -> Status | None:
        return await self.session.scalar(select(Status).where(func.lower(Status.ENG_NAME) == "active"))

    async def get_active_roles(self, role_codes: Sequence[str]) -> list[Role]:
        statement = select(Role).join(Status, Status.STATUS_ID == Role.STATUS_ID).where(Role.CODE.in_(role_codes), func.lower(Status.ENG_NAME) == "active")
        return list((await self.session.scalars(statement)).all())

    async def get_roles_by_user_ids(self, user_ids: Sequence[int]) -> dict[int, list[str]]:
        if not user_ids:
            return {}
        statement = select(UserRole.USER_ID, Role.CODE).join(Role, Role.ROLE_ID == UserRole.ROLE_ID).where(UserRole.USER_ID.in_(user_ids)).order_by(UserRole.USER_ID, Role.CODE)
        roles: dict[int, list[str]] = {user_id: [] for user_id in user_ids}
        for user_id, code in (await self.session.execute(statement)).all():
            roles[user_id].append(code)
        return roles

    async def create_user(self, user: User, roles: Sequence[Role]) -> User:
        self.session.add(user)
        await self.session.flush()
        self.session.add_all(UserRole(USER_ID=user.USER_ID, ROLE_ID=role.ROLE_ID) for role in roles)
        await self.session.flush()
        return user

    async def replace_roles(self, user_id: int, roles: Sequence[Role]) -> None:
        await self.session.execute(delete(UserRole).where(UserRole.USER_ID == user_id))
        self.session.add_all(UserRole(USER_ID=user_id, ROLE_ID=role.ROLE_ID) for role in roles)
        await self.session.flush()
