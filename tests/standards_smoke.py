"""End-to-end standards API smoke test."""

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
from app.modules.ols.models import OlsParameter, OlsSurfaceType, Standard, StandardType
from app.modules.users.models import Role, User, UserRole


BASE_URL = "http://localhost:8000/api/v1"


def call(path, method="GET", data=None, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    body = json.dumps(data).encode() if data is not None else None
    if data is not None:
        headers["Content-Type"] = "application/json"
    try:
        with urlopen(
            Request(BASE_URL + path, data=body, headers=headers, method=method),
            timeout=15,
        ) as response:
            content = response.read()
            return response.status, json.loads(content) if content else None
    except HTTPError as exc:
        content = exc.read()
        return exc.code, json.loads(content) if content else None


def login(username, password):
    body = urlencode({"username": username, "password": password}).encode()
    with urlopen(
        Request(
            BASE_URL + "/auth/login",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        ),
        timeout=15,
    ) as response:
        return json.loads(response.read())["access_token"]


async def main():
    suffix = uuid4().hex[:8]
    username = f"standards_admin_{suffix}"
    password = f"Standards-{uuid4().hex}!"
    standard_id = None
    async with AsyncSessionFactory() as session:
        active = await session.scalar(
            select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "active")
        )
        inactive = await session.scalar(
            select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "inactive")
        )
        admin_role = await session.scalar(
            select(Role.ROLE_ID).where(Role.CODE == "ADMIN")
        )
        assert active and inactive and admin_role
        surface_type_id = await session.scalar(
            select(OlsSurfaceType.SURFACE_TYPE_ID).where(OlsSurfaceType.CODE == "APPROACH")
        )
        parameter_id = await session.scalar(
            select(OlsParameter.PARAMETER_ID).where(OlsParameter.CODE == "LENGTH")
        )
        assert surface_type_id and parameter_id
        standard_type = StandardType(
            CODE=f"ICAO_{suffix}",
            AZE_NAME="Test standart tipi",
            ENG_NAME="Test standard type",
            DESCRIPTION="Smoke test",
            STATUS_ID=active,
        )
        user = User(
            USERNAME=username,
            EMAIL=f"{username}@example.com",
            PASSWORD_HASH=hash_password(password),
            FIRST_NAME="Standards",
            LAST_NAME="Admin",
            STATUS_ID=active,
        )
        session.add_all([standard_type, user])
        await session.flush()
        session.add(UserRole(USER_ID=user.USER_ID, ROLE_ID=admin_role))
        await session.commit()
        type_id, user_id = standard_type.STANDARD_TYPE_ID, user.USER_ID
        try:
            token = login(username, password)
            payload = {
                "standard_type_id": type_id,
                "code": f"icao-annex-14-{suffix}",
                "aze_name": "ICAO Əlavə 14",
                "eng_name": "ICAO Annex 14",
                "edition": "9",
                "amendment": "17",
                "effective_date": "2025-11-27",
                "description": "Aerodromes, Volume I",
            }
            code, created = call("/standards", "POST", payload, token)
            assert code == 201 and created
            standard_id = int(created["standard_id"])
            assert created["code"] == payload["code"].upper()
            code, configurations = call(
                f"/standards/{standard_id}/ols-configurations",
                "POST",
                {"surface_type_id": surface_type_id, "description": "Smoke test surface"},
                token,
            )
            assert code == 201 and configurations["total"] == 1
            configuration_id = configurations["items"][0]["standard_ols_id"]
            code, configurations = call(
                f"/standards/{standard_id}/ols-configurations/{configuration_id}/parameters",
                "PUT",
                {
                    "parameter_id": parameter_id,
                    "section_no": 1,
                    "numeric_value": 3000,
                    "boolean_value": None,
                    "description": "Section 1",
                },
                token,
            )
            assert code == 200 and len(configurations["items"][0]["parameters"]) == 1
            param_value_id = configurations["items"][0]["parameters"][0]["param_value_id"]
            code, _ = call(
                f"/standards/{standard_id}/ols-configurations/{configuration_id}/parameters/{param_value_id}",
                "DELETE",
                token=token,
            )
            assert code == 204
            code, _ = call(
                f"/standards/{standard_id}/ols-configurations/{configuration_id}",
                "DELETE",
                token=token,
            )
            assert code == 204
            code, _ = call("/standards", "POST", payload, token)
            assert code == 409
            code, listed = call(
                f"/standards?search=annex&standard_type_id={type_id}", token=token
            )
            assert code == 200 and listed["total"] == 1
            code, updated = call(
                f"/standards/{standard_id}",
                "PATCH",
                {"edition": "10", "description": "Updated standard"},
                token,
            )
            assert code == 200 and updated["edition"] == "10"
            code, _ = call(
                f"/standards/{standard_id}/status",
                "PATCH",
                {"status_id": inactive},
                token,
            )
            assert code == 204
            code, inactive_item = call(f"/standards/{standard_id}", token=token)
            assert code == 200 and inactive_item["status"].lower() == "inactive"
            code, _ = call(f"/standards/{standard_id}", "DELETE", token=token)
            assert code == 204
            code, archived = call(f"/standards/{standard_id}", token=token)
            assert code == 200 and archived["status"].lower() == "archived"
        finally:
            if standard_id is not None:
                await session.execute(
                    delete(Standard).where(Standard.STANDARD_ID == standard_id)
                )
            await session.execute(delete(User).where(User.USER_ID == user_id))
            await session.execute(
                delete(StandardType).where(
                    StandardType.STANDARD_TYPE_ID == type_id
                )
            )
            await session.commit()
    await close_database()
    print("Standards smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())
