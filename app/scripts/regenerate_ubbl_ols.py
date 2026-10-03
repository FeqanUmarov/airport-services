"""Regenerate UBBL automatic OLS surfaces using the active standard."""

import asyncio

from sqlalchemy import select

import app.models  # noqa: F401 - register complete SQLAlchemy metadata
from app.core.database import AsyncSessionFactory, close_database
from app.modules.airports.models import Airport, IcaoCode
from app.modules.ols.models import Standard
from app.modules.ols.service import AutomaticOlsService
from app.modules.runways.models import Runway


async def main() -> None:
    async with AsyncSessionFactory() as session:
        run_id = await session.scalar(
            select(Runway.RUN_ID)
            .join(Airport, Airport.AIR_ID == Runway.AIR_ID)
            .join(IcaoCode, IcaoCode.ICAO_ID == Airport.ICAO_ID)
            .where(IcaoCode.ICAO_CODE == "UBBL")
        )
        standard_id = await session.scalar(
            select(Standard.STANDARD_ID).where(
                Standard.CODE == "ICAO_ANNEX_14_V1_ZANGILAN"
            )
        )
        if run_id is None or standard_id is None:
            raise RuntimeError("UBBL runway or active OLS standard was not found")
        result = await AutomaticOlsService(session).generate(
            standard_id=standard_id,
            run_id=run_id,
            replace_existing=True,
            revision_note="Regenerated after official UBBL AIP parameter update",
        )
        print(f"Generated {result.generated_count} UBBL OLS surfaces")
        for surface in result.surfaces:
            print(
                surface.surface_type,
                surface.run_dir_id,
                surface.topology_status,
                surface.topology_message or "",
            )
    await close_database()


if __name__ == "__main__":
    asyncio.run(main())
