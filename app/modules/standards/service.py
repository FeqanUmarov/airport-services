from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ols.models import Standard, StandardOlsParameterValue, StandardOlsSurface
from app.modules.standards.repository import StandardRepository
from app.modules.standards.schemas import (
    StandardCreate,
    StandardListResponse,
    StandardResponse,
    StandardParameterResponse,
    StandardParameterUpsert,
    StandardSurfaceCreate,
    StandardSurfaceListResponse,
    StandardSurfaceResponse,
)


class StandardNotFoundError(ValueError):
    pass


class StandardConflictError(ValueError):
    pass


class StandardValidationError(ValueError):
    pass


class StandardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = StandardRepository(session)

    @staticmethod
    def _response(row: Any) -> StandardResponse:
        item = row[0]
        return StandardResponse(
            standard_id=item.STANDARD_ID,
            standard_type_id=item.STANDARD_TYPE_ID,
            standard_type_code=row.standard_type_code,
            standard_type_name=row.standard_type_name,
            code=item.CODE,
            aze_name=item.AZE_NAME,
            eng_name=item.ENG_NAME,
            edition=item.EDITION,
            amendment=item.AMENDMENT,
            effective_date=item.EFFECTIVE_DATE,
            description=item.DESCRIPTION,
            status_id=item.STATUS_ID,
            status=row.status_name,
            created_date=item.CREATED_DATE,
            last_edited_date=item.LAST_EDITED_DATE,
        )

    async def list_items(self, **filters: Any) -> StandardListResponse:
        page = int(filters.pop("page"))
        page_size = int(filters.pop("page_size"))
        rows, total = await self.repository.list_items(
            offset=(page - 1) * page_size,
            limit=page_size,
            **filters,
        )
        return StandardListResponse(
            items=[self._response(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get(self, standard_id: int) -> StandardResponse:
        row = await self.repository.get_row(standard_id)
        if row is None:
            raise StandardNotFoundError("Standard does not exist")
        return self._response(row)

    async def _validate_type(self, standard_type_id: int) -> None:
        standard_type = await self.repository.standard_type(standard_type_id)
        if standard_type is None:
            raise StandardValidationError("Standard type does not exist")

    async def create(self, payload: StandardCreate) -> StandardResponse:
        await self._validate_type(payload.standard_type_id)
        if await self.repository.duplicate(
            code=payload.code,
            edition=payload.edition,
            amendment=payload.amendment,
        ):
            raise StandardConflictError(
                "A standard with this code, edition and amendment already exists"
            )
        active = await self.repository.status_by_name("active")
        if active is None:
            raise StandardValidationError("Active status is not configured")
        item = Standard(
            STANDARD_TYPE_ID=payload.standard_type_id,
            CODE=payload.code,
            AZE_NAME=payload.aze_name,
            ENG_NAME=payload.eng_name,
            EDITION=payload.edition,
            AMENDMENT=payload.amendment,
            EFFECTIVE_DATE=payload.effective_date,
            DESCRIPTION=payload.description,
            STATUS_ID=active.STATUS_ID,
        )
        self.session.add(item)
        await self.session.commit()
        return await self.get(item.STANDARD_ID)

    async def update(self, standard_id: int, changes: dict[str, Any]) -> StandardResponse:
        item = await self.repository.get_model(standard_id)
        if item is None:
            raise StandardNotFoundError("Standard does not exist")
        type_id = int(changes.get("standard_type_id", item.STANDARD_TYPE_ID))
        await self._validate_type(type_id)
        code = str(changes.get("code", item.CODE))
        edition = changes.get("edition", item.EDITION)
        amendment = changes.get("amendment", item.AMENDMENT)
        if await self.repository.duplicate(
            code=code,
            edition=str(edition) if edition is not None else None,
            amendment=str(amendment) if amendment is not None else None,
            exclude_id=standard_id,
        ):
            raise StandardConflictError(
                "A standard with this code, edition and amendment already exists"
            )
        fields = {
            "standard_type_id": "STANDARD_TYPE_ID",
            "code": "CODE",
            "aze_name": "AZE_NAME",
            "eng_name": "ENG_NAME",
            "edition": "EDITION",
            "amendment": "AMENDMENT",
            "effective_date": "EFFECTIVE_DATE",
            "description": "DESCRIPTION",
        }
        for source, target in fields.items():
            if source in changes:
                setattr(item, target, changes[source])
        await self.session.commit()
        return await self.get(standard_id)

    async def update_status(self, standard_id: int, status_id: int) -> None:
        item = await self.repository.get_model(standard_id)
        if item is None:
            raise StandardNotFoundError("Standard does not exist")
        if await self.repository.status(status_id) is None:
            raise StandardValidationError("Status does not exist")
        item.STATUS_ID = status_id
        await self.session.commit()

    async def archive(self, standard_id: int) -> None:
        item = await self.repository.get_model(standard_id)
        if item is None:
            raise StandardNotFoundError("Standard does not exist")
        archived = await self.repository.status_by_name("archived")
        if archived is None:
            raise StandardValidationError("Archived status is not configured")
        item.STATUS_ID = archived.STATUS_ID
        await self.session.commit()

    @staticmethod
    def _parameter_response(row: Any) -> StandardParameterResponse:
        item = row[0]
        return StandardParameterResponse(
            param_value_id=item.PARAM_VALUE_ID,
            parameter_id=item.PARAMETER_ID,
            parameter_code=row.parameter_code,
            parameter_name=row.parameter_name or row.parameter_code,
            section_no=item.SECTION_NO,
            numeric_value=item.NUMERIC_VALUE,
            boolean_value=item.BOOLEAN_VALUE,
            unit_id=row.unit_id,
            unit_code=row.unit_code,
            unit_symbol=row.unit_symbol,
            description=item.DESCRIPTION,
            status_id=item.STATUS_ID,
            status=row.status_name,
        )

    async def _surface_response(self, row: Any) -> StandardSurfaceResponse:
        item = row[0]
        parameters = await self.repository.parameters(item.STANDARD_OLS_ID)
        return StandardSurfaceResponse(
            standard_ols_id=item.STANDARD_OLS_ID,
            standard_id=item.STANDARD_ID,
            surface_type_id=item.SURFACE_TYPE_ID,
            surface_type_code=row.surface_type_code,
            surface_type_name=row.surface_type_name or row.surface_type_code,
            description=item.DESCRIPTION,
            status_id=item.STATUS_ID,
            status=row.status_name,
            parameters=[self._parameter_response(value) for value in parameters],
        )

    async def list_surfaces(self, standard_id: int) -> StandardSurfaceListResponse:
        await self.get(standard_id)
        rows = await self.repository.surfaces(standard_id)
        return StandardSurfaceListResponse(
            items=[await self._surface_response(row) for row in rows],
            total=len(rows),
        )

    async def create_surface(self, standard_id: int, payload: StandardSurfaceCreate) -> StandardSurfaceListResponse:
        await self.get(standard_id)
        if await self.repository.surface_type(payload.surface_type_id) is None:
            raise StandardValidationError("OLS surface type does not exist")
        existing = await self.repository.surface_by_type(standard_id, payload.surface_type_id)
        if existing is not None:
            raise StandardConflictError("This surface type is already configured for the standard")
        active = await self.repository.status_by_name("active")
        if active is None:
            raise StandardValidationError("Active status is not configured")
        self.session.add(StandardOlsSurface(
            STANDARD_ID=standard_id,
            SURFACE_TYPE_ID=payload.surface_type_id,
            DESCRIPTION=payload.description,
            STATUS_ID=active.STATUS_ID,
        ))
        await self.session.commit()
        return await self.list_surfaces(standard_id)

    async def update_surface(self, standard_id: int, standard_ols_id: int, changes: dict[str, Any]) -> StandardSurfaceListResponse:
        item = await self.repository.surface(standard_id, standard_ols_id)
        if item is None:
            raise StandardNotFoundError("Standard OLS surface does not exist")
        if "status_id" in changes and await self.repository.status(int(changes["status_id"])) is None:
            raise StandardValidationError("Status does not exist")
        if "description" in changes:
            item.DESCRIPTION = changes["description"]
        if "status_id" in changes:
            item.STATUS_ID = changes["status_id"]
        await self.session.commit()
        return await self.list_surfaces(standard_id)

    async def archive_surface(self, standard_id: int, standard_ols_id: int) -> None:
        item = await self.repository.surface(standard_id, standard_ols_id)
        if item is None:
            raise StandardNotFoundError("Standard OLS surface does not exist")
        archived = await self.repository.status_by_name("archived")
        if archived is None:
            raise StandardValidationError("Archived status is not configured")
        item.STATUS_ID = archived.STATUS_ID
        await self.session.commit()

    async def upsert_parameter(self, standard_id: int, standard_ols_id: int, payload: StandardParameterUpsert) -> StandardSurfaceListResponse:
        if await self.repository.surface(standard_id, standard_ols_id) is None:
            raise StandardNotFoundError("Standard OLS surface does not exist")
        if await self.repository.parameter_definition(payload.parameter_id) is None:
            raise StandardValidationError("OLS parameter does not exist")
        item = await self.repository.parameter_by_key(standard_ols_id, payload.parameter_id, payload.section_no)
        active = await self.repository.status_by_name("active")
        if active is None:
            raise StandardValidationError("Active status is not configured")
        if item is None:
            item = StandardOlsParameterValue(
                STANDARD_OLS_ID=standard_ols_id,
                PARAMETER_ID=payload.parameter_id,
                SECTION_NO=payload.section_no,
                STATUS_ID=active.STATUS_ID,
            )
            self.session.add(item)
        item.NUMERIC_VALUE = payload.numeric_value
        item.BOOLEAN_VALUE = payload.boolean_value
        item.DESCRIPTION = payload.description
        item.STATUS_ID = active.STATUS_ID
        await self.session.commit()
        return await self.list_surfaces(standard_id)

    async def archive_parameter(self, standard_id: int, standard_ols_id: int, param_value_id: int) -> None:
        if await self.repository.surface(standard_id, standard_ols_id) is None:
            raise StandardNotFoundError("Standard OLS surface does not exist")
        item = await self.repository.parameter_value(standard_ols_id, param_value_id)
        if item is None:
            raise StandardNotFoundError("Standard OLS parameter value does not exist")
        archived = await self.repository.status_by_name("archived")
        if archived is None:
            raise StandardValidationError("Archived status is not configured")
        item.STATUS_ID = archived.STATUS_ID
        await self.session.commit()
