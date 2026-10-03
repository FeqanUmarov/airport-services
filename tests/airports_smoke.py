"""End-to-end smoke test for airport CRUD, geometry, filters and roles."""

import asyncio
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

from sqlalchemy import delete, func, select

from app.core.database import AsyncSessionFactory, close_database
from app.core.security import hash_password
from app.modules.airports.models import Airport, City, Country, IcaoCode, Status
from app.modules.users.models import Role, User, UserRole


BASE_URL = "http://localhost:8000/api/v1"


def request_json(
    path: str,
    *,
    method: str = "GET",
    data: dict[str, object] | None = None,
    bearer: str | None = None,
) -> tuple[int, dict[str, object] | None]:
    headers: dict[str, str] = {}
    body = json.dumps(data).encode() if data is not None else None
    if data is not None:
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


def login(username: str, password: str) -> str:
    body = urlencode({"username": username, "password": password}).encode()
    with urlopen(
        Request(
            f"{BASE_URL}/auth/login",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        ),
        timeout=15,
    ) as response:
        return str(json.loads(response.read())["access_token"])


async def main() -> None:
    suffix = uuid4().hex[:8]
    admin_name = f"airport_admin_{suffix}"
    viewer_name = f"airport_viewer_{suffix}"
    password = f"Airport-{uuid4().hex}!"
    air_id: int | None = None

    async with AsyncSessionFactory() as session:
        active_id = await session.scalar(
            select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "active")
        )
        inactive_id = await session.scalar(
            select(Status.STATUS_ID).where(func.lower(Status.ENG_NAME) == "inactive")
        )
        admin_role = await session.scalar(select(Role.ROLE_ID).where(Role.CODE == "ADMIN"))
        viewer_role = await session.scalar(select(Role.ROLE_ID).where(Role.CODE == "VIEWER"))
        assert None not in (active_id, inactive_id, admin_role, viewer_role)

        country = Country(
            AZE_NAME=f"Test ölkə {suffix}",
            ENG_NAME=f"Test Country {suffix}",
            ISO_CODE=f"T{suffix[:4].upper()}",
            STATUS_ID=active_id,
        )
        session.add(country)
        await session.flush()
        city = City(
            COUNTRY_ID=country.COUNTRY_ID,
            AZE_NAME=f"Test şəhər {suffix}",
            ENG_NAME=f"Test City {suffix}",
            STATUS_ID=active_id,
        )
        icao = IcaoCode(
            ICAO_CODE=f"T{suffix[:3].upper()}",
            DESCRIPTION="Airport smoke test",
            STATUS_ID=active_id,
        )
        session.add_all([city, icao])
        await session.flush()
        country_id, city_id, icao_id = country.COUNTRY_ID, city.CITY_ID, icao.ICAO_ID

        users = []
        for username, role_id in ((admin_name, admin_role), (viewer_name, viewer_role)):
            user = User(
                USERNAME=username,
                EMAIL=f"{username}@example.com",
                PASSWORD_HASH=hash_password(password),
                FIRST_NAME="Airport",
                LAST_NAME="Smoke",
                STATUS_ID=active_id,
            )
            session.add(user)
            await session.flush()
            users.append(user.USER_ID)
            session.add(UserRole(USER_ID=user.USER_ID, ROLE_ID=role_id))
        await session.commit()

        try:
            admin_token = login(admin_name, password)
            viewer_token = login(viewer_name, password)
            payload = {
                "icao_id": icao_id,
                "iata_code": "TST",
                "aze_name": "Test Hava Limanı",
                "eng_name": "Test Airport",
                "country_id": country_id,
                "city_id": city_id,
                "elevation_m": "28.500",
                "arp_geom": {"type": "Point", "coordinates": [49.9, 40.4]},
                "boundary_geom": {
                    "type": "Polygon",
                    "coordinates": [[[49.8, 40.3], [50.0, 40.3], [50.0, 40.5], [49.8, 40.5], [49.8, 40.3]]],
                },
            }
            code, _ = request_json(
                "/airports", method="POST", data=payload, bearer=viewer_token
            )
            assert code == 403

            code, created = request_json(
                "/airports", method="POST", data=payload, bearer=admin_token
            )
            assert code == 201 and created is not None
            air_id = int(created["air_id"])
            assert created["arp_geom"]["type"] == "Point"
            assert created["boundary_geom"]["type"] == "Polygon"

            code, _ = request_json(
                "/airports", method="POST", data=payload, bearer=admin_token
            )
            assert code == 409

            code, listed = request_json(
                f"/airports?search={suffix[:3]}&country_id={country_id}",
                bearer=viewer_token,
            )
            assert code == 200 and listed is not None and listed["total"] == 1

            code, updated = request_json(
                f"/airports/{air_id}",
                method="PATCH",
                data={
                    "eng_name": "Updated Test Airport",
                    "elevation_m": "30.125",
                    "arp_geom": payload["arp_geom"],
                    "boundary_geom": payload["boundary_geom"],
                },
                bearer=admin_token,
            )
            assert code == 200 and updated is not None
            assert updated["eng_name"] == "Updated Test Airport"
            assert updated["elevation_m"] == "30.125"
            assert updated["arp_geom"] == payload["arp_geom"]

            code, changed = request_json(
                f"/airports/{air_id}/status",
                method="PATCH",
                data={"status_id": inactive_id},
                bearer=admin_token,
            )
            assert code == 200 and changed is not None
            assert changed["status"].lower() == "inactive"

            code, _ = request_json(
                f"/airports/{air_id}", method="DELETE", bearer=admin_token
            )
            assert code == 204
            code, archived = request_json(f"/airports/{air_id}", bearer=viewer_token)
            assert code == 200 and archived is not None
            assert archived["status"].lower() == "archived"
        finally:
            if air_id is not None:
                await session.execute(delete(Airport).where(Airport.AIR_ID == air_id))
            await session.execute(delete(User).where(User.USER_ID.in_(users)))
            await session.execute(delete(City).where(City.CITY_ID == city_id))
            await session.execute(delete(IcaoCode).where(IcaoCode.ICAO_ID == icao_id))
            await session.execute(delete(Country).where(Country.COUNTRY_ID == country_id))
            await session.commit()

    await close_database()
    print("Airports smoke test passed.")


if __name__ == "__main__":
    asyncio.run(main())
