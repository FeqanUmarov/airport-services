"""End-to-end smoke test for all dictionary endpoints."""

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
ENDPOINTS = (
    "statuses",
    "roles",
    "countries",
    "cities",
    "icao-codes",
    "standard-types",
    "ols-surface-types",
    "ols-generation-methods",
    "units",
    "ols-parameters",
    "obstacle-types",
    "runway-area-types",
)


def request(path: str, bearer: str | None = None) -> tuple[int, dict[str, object] | None]:
    headers = {"Authorization": f"Bearer {bearer}"} if bearer else {}
    try:
        with urlopen(Request(f"{BASE_URL}{path}", headers=headers), timeout=15) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except HTTPError as exc:
        content = exc.read()
        return exc.code, json.loads(content) if content else None


def login(username: str, password: str) -> str:
    body = urlencode({"username": username, "password": password}).encode()
    request_object = Request(
        f"{BASE_URL}/auth/login",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urlopen(request_object, timeout=15) as response:
        return str(json.loads(response.read())["access_token"])


async def main() -> None:
    suffix = uuid4().hex[:10]
    username = f"dictionary_smoke_{suffix}"
    password = f"Dictionary-{uuid4().hex}!"

    async with AsyncSessionFactory() as session:
        active_id = await session.scalar(
            select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "active")
        )
        viewer_id = await session.scalar(select(Role.ROLE_ID).where(Role.CODE == "VIEWER"))
        assert active_id is not None and viewer_id is not None
        user = User(
            USERNAME=username,
            EMAIL=f"{username}@example.com",
            PASSWORD_HASH=hash_password(password),
            FIRST_NAME="Dictionary",
            LAST_NAME="Smoke",
            STATUS_ID=active_id,
        )
        session.add(user)
        await session.flush()
        user_id = user.USER_ID
        session.add(UserRole(USER_ID=user_id, ROLE_ID=viewer_id))
        await session.commit()

        try:
            code, _ = request("/dictionaries/statuses")
            assert code == 401

            access_token = login(username, password)
            for endpoint in ENDPOINTS:
                code, payload = request(f"/dictionaries/{endpoint}", access_token)
                assert code == 200, (endpoint, code, payload)
                assert payload is not None
                assert isinstance(payload["items"], list)
                assert payload["total"] == len(payload["items"])

            code, statuses = request("/dictionaries/statuses", access_token)
            assert code == 200 and statuses is not None and statuses["total"] >= 3
            code, methods = request(
                "/dictionaries/ols-generation-methods",
                access_token,
            )
            assert code == 200 and methods is not None and methods["total"] >= 2
        finally:
            await session.execute(delete(User).where(User.USER_ID == user_id))
            await session.commit()

    await close_database()
    print("Dictionaries smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())
