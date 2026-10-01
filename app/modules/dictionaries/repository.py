from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import City, Country, IcaoCode, Status
from app.modules.obstacles.models import ObstacleType
from app.modules.ols.models import (
    OlsGenerationMethod,
    OlsParameter,
    OlsSurfaceType,
    StandardType,
    Unit,
)
from app.modules.runways.models import RunwayAreaType
from app.modules.users.models import Role


@dataclass(frozen=True)
class DictionarySpec:
    model: type[Any]
    id_field: str
    code_field: str | None = "CODE"
    parent_field: str | None = None
    symbol_field: str | None = None
    has_status: bool = True


DICTIONARIES: dict[str, DictionarySpec] = {
    "statuses": DictionarySpec(Status, "STATUS_ID", code_field=None, has_status=False),
    "roles": DictionarySpec(Role, "ROLE_ID"),
    "countries": DictionarySpec(Country, "COUNTRY_ID", code_field="ISO_CODE"),
    "cities": DictionarySpec(City, "CITY_ID", code_field=None, parent_field="COUNTRY_ID"),
    "icao-codes": DictionarySpec(IcaoCode, "ICAO_ID", code_field="ICAO_CODE"),
    "standard-types": DictionarySpec(StandardType, "STANDARD_TYPE_ID"),
    "ols-surface-types": DictionarySpec(OlsSurfaceType, "SURFACE_TYPE_ID"),
    "ols-generation-methods": DictionarySpec(
        OlsGenerationMethod,
        "GENERATION_METHOD_ID",
    ),
    "units": DictionarySpec(Unit, "UNIT_ID", symbol_field="SYMBOL"),
    "ols-parameters": DictionarySpec(
        OlsParameter,
        "PARAMETER_ID",
        parent_field="UNIT_ID",
    ),
    "obstacle-types": DictionarySpec(ObstacleType, "OBSTACLE_TYPE_ID"),
    "runway-area-types": DictionarySpec(RunwayAreaType, "AREA_TYPE_ID"),
}


class DictionaryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_items(
        self,
        name: str,
        *,
        active_only: bool,
        parent_id: int | None = None,
    ) -> tuple[DictionarySpec, list[Any]]:
        spec = DICTIONARIES[name]
        statement = select(spec.model)
        if spec.has_status and active_only:
            statement = statement.join(
                Status,
                Status.STATUS_ID == getattr(spec.model, "STATUS_ID"),
            ).where(func.lower(Status.ENG_NAME) == "active")
        if parent_id is not None and spec.parent_field is not None:
            statement = statement.where(
                getattr(spec.model, spec.parent_field) == parent_id
            )
        statement = statement.order_by(getattr(spec.model, spec.id_field))
        return spec, list((await self.session.scalars(statement)).all())
