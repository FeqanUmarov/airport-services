"""Rebuild UBBL Clearways from the active Strip using official AIP dimensions."""

import asyncio
from decimal import Decimal

from sqlalchemy import select

import app.models  # noqa: F401 - register complete SQLAlchemy metadata
from app.core.database import AsyncSessionFactory, close_database
from app.modules.airports.models import Airport, IcaoCode
from app.modules.runways.models import Runway, RunwayDirection
from app.modules.runways.schemas import ClearwayGenerateRequest
from app.modules.runways.service import RunwayService


async def main() -> None:
    async with AsyncSessionFactory() as session:
        direction_ids = list(
            (
                await session.scalars(
                    select(RunwayDirection.RUN_DIR_ID)
                    .join(Runway, Runway.RUN_ID == RunwayDirection.RUN_ID)
                    .join(Airport, Airport.AIR_ID == Runway.AIR_ID)
                    .join(IcaoCode, IcaoCode.ICAO_ID == Airport.ICAO_ID)
                    .where(
                        IcaoCode.ICAO_CODE == "UBBL",
                        RunwayDirection.DESIGNATOR.in_(("15", "33")),
                    )
                    .order_by(RunwayDirection.DESIGNATOR)
                )
            ).all()
        )
        if len(direction_ids) != 2:
            raise RuntimeError("Expected UBBL runway directions 15 and 33")
        service = RunwayService(session)
        for direction_id in direction_ids:
            await service.regenerate_clearway(
                direction_id,
                ClearwayGenerateRequest(
                    length_m=Decimal("300"),
                    width_m=Decimal("160"),
                ),
            )
    await close_database()


if __name__ == "__main__":
    asyncio.run(main())
