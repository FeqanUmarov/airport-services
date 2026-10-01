"""End-to-end users API smoke test with disposable accounts."""

import asyncio
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionFactory, close_database
from app.core.security import hash_password
from app.modules.airports.models import Status
from app.modules.users.models import Role, User, UserRole


BASE_URL = "http://localhost:8000/api/v1"


def request_json(
    path: str,
    *,
    method: str = "GET",
    data: dict[str, object] | None = None,
    bearer: str | None = None,
    form: bool = False,
) -> tuple[int, dict[str, object] | None]:
    headers: dict[str, str] = {}
    body = None
    if data is not None:
        if form:
            body = urlencode({key: str(value) for key, value in data.items()}).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    try:
        with urlopen(
            Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method),
            timeout=15,
        ) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except HTTPError as exc:
        content = exc.read()
        return exc.code, json.loads(content) if content else None


async def main() -> None:
    suffix = uuid4().hex[:10]
    admin_name = f"users_admin_{suffix}"
    target_name = f"users_target_{suffix}"
    admin_password = f"Admin-{uuid4().hex}!"
    target_password = f"Target-{uuid4().hex}!"
    new_password = f"Reset-{uuid4().hex}!"
    target_id: int | None = None

    async with AsyncSessionFactory() as session:
        active_id = await session.scalar(
            select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "active")
        )
        inactive_id = await session.scalar(
            select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "inactive")
        )
        admin_role_id = await session.scalar(
            select(Role.ROLE_ID).where(Role.CODE == "ADMIN")
        )
        assert active_id is not None and inactive_id is not None and admin_role_id is not None

        admin = User(
            USERNAME=admin_name,
            EMAIL=f"{admin_name}@example.com",
            PASSWORD_HASH=hash_password(admin_password),
            FIRST_NAME="Users",
            LAST_NAME="Admin",
            STATUS_ID=active_id,
        )
        session.add(admin)
        await session.flush()
        admin_id = admin.USER_ID
        session.add(UserRole(USER_ID=admin_id, ROLE_ID=admin_role_id))
        await session.commit()

        try:
            code, login = request_json(
                "/auth/login",
                method="POST",
                data={"username": admin_name, "password": admin_password},
                form=True,
            )
            assert code == 200 and login is not None
            admin_access = str(login["access_token"])

            code, created = request_json(
                "/users",
                method="POST",
                bearer=admin_access,
                data={
                    "username": target_name,
                    "email": f"{target_name}@example.com",
                    "password": target_password,
                    "first_name": "Target",
                    "last_name": "User",
                    "role_codes": ["VIEWER"],
                },
            )
            assert code == 201 and created is not None
            target_id = int(created["user_id"])
            assert created["roles"] == ["VIEWER"]

            code, duplicate = request_json(
                "/users",
                method="POST",
                bearer=admin_access,
                data={
                    "username": target_name,
                    "email": f"other_{suffix}@example.com",
                    "password": target_password,
                    "first_name": "Duplicate",
                    "last_name": "User",
                    "role_codes": ["VIEWER"],
                },
            )
            assert code == 409 and duplicate is not None

            code, listed = request_json(
                f"/users?search={target_name}&page=1&page_size=10",
                bearer=admin_access,
            )
            assert code == 200 and listed is not None and listed["total"] == 1

            code, target_login = request_json(
                "/auth/login",
                method="POST",
                data={"username": target_name, "password": target_password},
                form=True,
            )
            assert code == 200 and target_login is not None
            old_refresh = str(target_login["refresh_token"])
            code, _ = request_json(
                "/users",
                bearer=str(target_login["access_token"]),
            )
            assert code == 403

            code, updated = request_json(
                f"/users/{target_id}",
                method="PATCH",
                bearer=admin_access,
                data={"first_name": "Updated", "last_name": "Person"},
            )
            assert code == 200 and updated is not None
            assert updated["first_name"] == "Updated"

            code, roles = request_json(
                f"/users/{target_id}/roles",
                method="PUT",
                bearer=admin_access,
                data={"role_codes": ["EDITOR"]},
            )
            assert code == 200 and roles is not None and roles["roles"] == ["EDITOR"]

            code, _ = request_json(
                f"/users/{target_id}/reset-password",
                method="POST",
                bearer=admin_access,
                data={"new_password": new_password},
            )
            assert code == 204
            code, _ = request_json(
                "/auth/refresh", method="POST", data={"refresh_token": old_refresh}
            )
            assert code == 401

            code, new_login = request_json(
                "/auth/login",
                method="POST",
                data={"username": target_name, "password": new_password},
                form=True,
            )
            assert code == 200 and new_login is not None
            code, _ = request_json(
                f"/users/{target_id}/revoke-tokens",
                method="POST",
                bearer=admin_access,
            )
            assert code == 204
            code, _ = request_json(
                "/auth/refresh",
                method="POST",
                data={"refresh_token": str(new_login["refresh_token"])},
            )
            assert code == 401

            code, changed_status = request_json(
                f"/users/{target_id}/status",
                method="PATCH",
                bearer=admin_access,
                data={"status_id": inactive_id},
            )
            assert code == 200 and changed_status is not None
            assert changed_status["status"].lower() == "inactive"
            code, _ = request_json(
                "/auth/login",
                method="POST",
                data={"username": target_name, "password": new_password},
                form=True,
            )
            assert code == 401
        finally:
            ids = [admin_id]
            if target_id is not None:
                ids.append(target_id)
            await session.execute(delete(User).where(User.USER_ID.in_(ids)))
            await session.commit()

    await close_database()
    print("Users smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())
