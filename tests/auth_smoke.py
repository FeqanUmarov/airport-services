"""End-to-end auth smoke test using a disposable database user."""

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


BASE_URL = "http://localhost:8000/api/v1/auth"


def request_json(
    path: str,
    *,
    method: str = "GET",
    data: dict[str, str] | None = None,
    bearer: str | None = None,
    form: bool = False,
) -> tuple[int, dict[str, object] | None]:
    headers: dict[str, str] = {}
    body = None
    if data is not None:
        if form:
            body = urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"

    try:
        with urlopen(
            Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method),
            timeout=10,
        ) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except HTTPError as exc:
        content = exc.read()
        return exc.code, json.loads(content) if content else None


async def main() -> None:
    suffix = uuid4().hex[:10]
    username = f"auth_smoke_{suffix}"
    email = f"{username}@example.com"
    password = f"Smoke-{uuid4().hex}!"
    new_password = f"Changed-{uuid4().hex}!"

    async with AsyncSessionFactory() as session:
        active_status_id = await session.scalar(
            select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "active")
        )
        viewer_role_id = await session.scalar(select(Role.ROLE_ID).where(Role.CODE == "VIEWER"))
        assert active_status_id is not None and viewer_role_id is not None

        user = User(
            USERNAME=username,
            EMAIL=email,
            PASSWORD_HASH=hash_password(password),
            FIRST_NAME="Auth",
            LAST_NAME="Smoke",
            STATUS_ID=active_status_id,
        )
        session.add(user)
        await session.flush()
        user_id = user.USER_ID
        session.add(UserRole(USER_ID=user_id, ROLE_ID=viewer_role_id))
        await session.commit()

        try:
            status, login = request_json(
                "/login",
                method="POST",
                data={"username": username, "password": password},
                form=True,
            )
            assert status == 200 and login is not None

            status, me = request_json("/me", bearer=str(login["access_token"]))
            assert status == 200 and me is not None
            assert me["username"] == username and me["roles"] == ["VIEWER"]

            old_refresh = str(login["refresh_token"])
            status, refreshed = request_json(
                "/refresh",
                method="POST",
                data={"refresh_token": old_refresh},
            )
            assert status == 200 and refreshed is not None

            status, _ = request_json(
                "/refresh",
                method="POST",
                data={"refresh_token": old_refresh},
            )
            assert status == 401

            new_refresh = str(refreshed["refresh_token"])
            status, _ = request_json(
                "/logout",
                method="POST",
                data={"refresh_token": new_refresh},
            )
            assert status == 204

            status, _ = request_json(
                "/refresh",
                method="POST",
                data={"refresh_token": new_refresh},
            )
            assert status == 401

            status, second_login = request_json(
                "/login",
                method="POST",
                data={"username": username, "password": password},
                form=True,
            )
            assert status == 200 and second_login is not None

            status, _ = request_json(
                "/change-password",
                method="POST",
                data={
                    "current_password": password,
                    "new_password": new_password,
                },
                bearer=str(second_login["access_token"]),
            )
            assert status == 204

            status, _ = request_json(
                "/refresh",
                method="POST",
                data={"refresh_token": str(second_login["refresh_token"])},
            )
            assert status == 401

            status, _ = request_json(
                "/login",
                method="POST",
                data={"username": username, "password": password},
                form=True,
            )
            assert status == 401

            status, third_login = request_json(
                "/login",
                method="POST",
                data={"username": username, "password": new_password},
                form=True,
            )
            assert status == 200 and third_login is not None

            status, _ = request_json(
                "/logout-all",
                method="POST",
                bearer=str(third_login["access_token"]),
            )
            assert status == 204

            status, _ = request_json(
                "/refresh",
                method="POST",
                data={"refresh_token": str(third_login["refresh_token"])},
            )
            assert status == 401
        finally:
            await session.execute(delete(User).where(User.USER_ID == user_id))
            await session.commit()

    await close_database()
    print("Auth smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())
