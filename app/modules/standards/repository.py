from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.airports.models import Status
from app.modules.ols.models import (
    OlsParameter,
    OlsSurfaceType,
    Standard,
    StandardOlsParameterValue,
    StandardOlsSurface,
    StandardType,
    Unit,
)


class StandardRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def details_statement():
        return (
            select(
                Standard,
                StandardType.CODE.label("standard_type_code"),
                StandardType.ENG_NAME.label("standard_type_name"),
                Status.ENG_NAME.label("status_name"),
            )
            .join(
                StandardType,
                StandardType.STANDARD_TYPE_ID == Standard.STANDARD_TYPE_ID,
            )
            .join(Status, Status.STATUS_ID == Standard.STATUS_ID)
        )

    async def list_items(
        self,
        *,
        offset: int,
        limit: int,
        search: str | None,
        standard_type_id: int | None,
        status_id: int | None,
    ):
        conditions = []
        if search:
            pattern = f"%{search.strip().lower()}%"
            conditions.append(
                or_(
                    func.lower(Standard.CODE).like(pattern),
                    func.lower(Standard.AZE_NAME).like(pattern),
                    func.lower(Standard.ENG_NAME).like(pattern),
                )
            )
        if standard_type_id is not None:
            conditions.append(Standard.STANDARD_TYPE_ID == standard_type_id)
        if status_id is not None:
            conditions.append(Standard.STATUS_ID == status_id)
        total = int(
            (
                await self.session.scalar(
                    select(func.count(Standard.STANDARD_ID)).where(*conditions)
                )
            )
            or 0
        )
        rows = (
            await self.session.execute(
                self.details_statement()
                .where(*conditions)
                .order_by(Standard.EFFECTIVE_DATE.desc(), Standard.STANDARD_ID.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return list(rows), total

    async def get_row(self, standard_id: int):
        return (
            await self.session.execute(
                self.details_statement().where(Standard.STANDARD_ID == standard_id)
            )
        ).one_or_none()

    async def get_model(self, standard_id: int) -> Standard | None:
        return await self.session.get(Standard, standard_id)

    async def standard_type(self, standard_type_id: int) -> StandardType | None:
        return await self.session.get(StandardType, standard_type_id)

    async def status(self, status_id: int) -> Status | None:
        return await self.session.get(Status, status_id)

    async def status_by_name(self, name: str) -> Status | None:
        return await self.session.scalar(
            select(Status).where(func.lower(Status.ENG_NAME) == name.casefold())
        )

    async def duplicate(
        self,
        *,
        code: str,
        edition: str | None,
        amendment: str | None,
        exclude_id: int | None = None,
    ) -> Standard | None:
        statement = select(Standard).where(
            func.lower(Standard.CODE) == code.lower(),
            func.coalesce(Standard.EDITION, "") == (edition or ""),
            func.coalesce(Standard.AMENDMENT, "") == (amendment or ""),
        )
        if exclude_id is not None:
            statement = statement.where(Standard.STANDARD_ID != exclude_id)
        return await self.session.scalar(statement)

    async def surface_type(self, surface_type_id: int) -> OlsSurfaceType | None:
        return await self.session.get(OlsSurfaceType, surface_type_id)

    async def surface(self, standard_id: int, standard_ols_id: int) -> StandardOlsSurface | None:
        return await self.session.scalar(
            select(StandardOlsSurface).where(
                StandardOlsSurface.STANDARD_ID == standard_id,
                StandardOlsSurface.STANDARD_OLS_ID == standard_ols_id,
            )
        )

    async def surface_by_type(self, standard_id: int, surface_type_id: int) -> StandardOlsSurface | None:
        return await self.session.scalar(
            select(StandardOlsSurface).where(
                StandardOlsSurface.STANDARD_ID == standard_id,
                StandardOlsSurface.SURFACE_TYPE_ID == surface_type_id,
            )
        )

    async def surfaces(self, standard_id: int):
        return list((await self.session.execute(
            select(
                StandardOlsSurface,
                OlsSurfaceType.CODE.label("surface_type_code"),
                OlsSurfaceType.AZE_NAME.label("surface_type_name"),
                Status.ENG_NAME.label("status_name"),
            )
            .join(OlsSurfaceType, OlsSurfaceType.SURFACE_TYPE_ID == StandardOlsSurface.SURFACE_TYPE_ID)
            .join(Status, Status.STATUS_ID == StandardOlsSurface.STATUS_ID)
            .where(StandardOlsSurface.STANDARD_ID == standard_id)
            .order_by(OlsSurfaceType.SURFACE_TYPE_ID)
        )).all())

    async def parameter_definition(self, parameter_id: int) -> OlsParameter | None:
        return await self.session.get(OlsParameter, parameter_id)

    async def parameter_value(self, standard_ols_id: int, param_value_id: int) -> StandardOlsParameterValue | None:
        return await self.session.scalar(
            select(StandardOlsParameterValue).where(
                StandardOlsParameterValue.STANDARD_OLS_ID == standard_ols_id,
                StandardOlsParameterValue.PARAM_VALUE_ID == param_value_id,
            )
        )

    async def parameter_by_key(self, standard_ols_id: int, parameter_id: int, section_no: int) -> StandardOlsParameterValue | None:
        return await self.session.scalar(
            select(StandardOlsParameterValue).where(
                StandardOlsParameterValue.STANDARD_OLS_ID == standard_ols_id,
                StandardOlsParameterValue.PARAMETER_ID == parameter_id,
                StandardOlsParameterValue.SECTION_NO == section_no,
            )
        )

    async def parameters(self, standard_ols_id: int):
        return list((await self.session.execute(
            select(
                StandardOlsParameterValue,
                OlsParameter.CODE.label("parameter_code"),
                OlsParameter.AZE_NAME.label("parameter_name"),
                Unit.UNIT_ID.label("unit_id"),
                Unit.CODE.label("unit_code"),
                Unit.SYMBOL.label("unit_symbol"),
                Status.ENG_NAME.label("status_name"),
            )
            .join(OlsParameter, OlsParameter.PARAMETER_ID == StandardOlsParameterValue.PARAMETER_ID)
            .join(Unit, Unit.UNIT_ID == OlsParameter.UNIT_ID)
            .join(Status, Status.STATUS_ID == StandardOlsParameterValue.STATUS_ID)
            .where(StandardOlsParameterValue.STANDARD_OLS_ID == standard_ols_id)
            .order_by(StandardOlsParameterValue.SECTION_NO, OlsParameter.PARAMETER_ID)
        )).all())
