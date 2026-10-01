"""Dashboard overview end-to-end smoke test with a disposable viewer."""
import asyncio
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionFactory, close_database
from app.core.security import hash_password
from app.modules.airports.models import Status
from app.modules.users.models import Role, User, UserRole


BASE_URL = "http://localhost:8000/api/v1"


def request(path: str, *, token: str | None = None, form: dict[str, str] | None = None) -> tuple[int, dict]:
    headers: dict[str, str] = {}
    body = None
    method = "GET"
    if form is not None:
        body = urlencode(form).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
        method = "POST"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    with urlopen(Request(BASE_URL + path, data=body, headers=headers, method=method), timeout=20) as response:
        return response.status, json.loads(response.read())


async def main() -> None:
    suffix = uuid4().hex[:10]
    username = f"dashboard_{suffix}"
    password = f"Dashboard-{uuid4().hex}!"
    async with AsyncSessionFactory() as session:
        active_id = await session.scalar(select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "active"))
        role_id = await session.scalar(select(Role.ROLE_ID).where(Role.CODE == "VIEWER"))
        assert active_id is not None and role_id is not None
        user = User(USERNAME=username, EMAIL=f"{username}@example.com", PASSWORD_HASH=hash_password(password), FIRST_NAME="Dashboard", LAST_NAME="Viewer", STATUS_ID=active_id)
        session.add(user)
        await session.flush()
        user_id = user.USER_ID
        session.add(UserRole(USER_ID=user_id, ROLE_ID=role_id))
        await session.commit()
        try:
            code, tokens = request("/auth/login", form={"username": username, "password": password})
            assert code == 200
            code, payload = request("/dashboard/overview", token=tokens["access_token"])
            assert code == 200
            assert set(payload["totals"]) == {"airports", "runways", "ols_surfaces", "obstacles", "violations", "standards"}
            assert all(value >= 0 for value in payload["totals"].values())
            assert isinstance(payload["airports"], list)
            assert isinstance(payload["ols_by_type"], dict)
            assert isinstance(payload["recent_obstacles"], list)
            assert isinstance(payload["recent_violations"], list)
        finally:
            await session.execute(delete(User).where(User.USER_ID == user_id))
            await session.commit()
    await close_database()
    print("Dashboard smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())
