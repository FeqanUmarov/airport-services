from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.declared_distances.models import DeclaredDistance
from app.modules.declared_distances.repository import DeclaredDistanceRepository
from app.modules.declared_distances.schemas import (
    DeclaredDistanceResponse,
    DeclaredDistanceUpsert,
)


class DeclaredDistanceNotFoundError(ValueError):
    pass


class DeclaredDistanceValidationError(ValueError):
    pass


class DeclaredDistanceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = DeclaredDistanceRepository(session)

    @staticmethod
    def _response(row) -> DeclaredDistanceResponse:
        item = row[0]
        return DeclaredDistanceResponse(
            declared_distance_id=item.DECLARED_DISTANCE_ID,
            run_dir_id=item.RUN_DIR_ID,
            run_id=row.RUN_ID,
            designator=row.DESIGNATOR,
            tora_m=item.TORA_M,
            toda_m=item.TODA_M,
            asda_m=item.ASDA_M,
            lda_m=item.LDA_M,
            status_id=item.STATUS_ID,
            status=row.status_name,
            created_date=item.CREATED_DATE,
            last_edited_date=item.LAST_EDITED_DATE,
        )

    async def get(self, direction_id: int) -> DeclaredDistanceResponse:
        row = await self.repository.get_row_by_direction(direction_id)
        if row is None:
            if not await self.repository.direction_exists(direction_id):
                raise DeclaredDistanceNotFoundError("Runway direction does not exist")
            raise DeclaredDistanceNotFoundError(
                "Declared distances are not configured for this direction"
            )
        return self._response(row)

    async def upsert(
        self,
        direction_id: int,
        payload: DeclaredDistanceUpsert,
    ) -> DeclaredDistanceResponse:
        if not await self.repository.direction_exists(direction_id):
            raise DeclaredDistanceNotFoundError("Runway direction does not exist")
        item = await self.repository.get_model_by_direction(direction_id)
        if item is None:
            active = await self.repository.status_by_name("active")
            if active is None:
                raise DeclaredDistanceValidationError("Active status is not configured")
            item = DeclaredDistance(RUN_DIR_ID=direction_id, STATUS_ID=active.STATUS_ID)
            self.session.add(item)
        item.TORA_M = payload.tora_m
        item.TODA_M = payload.toda_m
        item.ASDA_M = payload.asda_m
        item.LDA_M = payload.lda_m
        await self.session.commit()
        return await self.get(direction_id)

    async def update_status(self, direction_id: int, status_id: int) -> None:
        item = await self.repository.get_model_by_direction(direction_id)
        if item is None:
            raise DeclaredDistanceNotFoundError(
                "Declared distances are not configured for this direction"
            )
        if await self.repository.get_status(status_id) is None:
            raise DeclaredDistanceValidationError("Status does not exist")
        item.STATUS_ID = status_id
        await self.session.commit()

    async def archive(self, direction_id: int) -> None:
        item = await self.repository.get_model_by_direction(direction_id)
        if item is None:
            raise DeclaredDistanceNotFoundError(
                "Declared distances are not configured for this direction"
            )
        archived = await self.repository.status_by_name("archived")
        if archived is None:
            raise DeclaredDistanceValidationError("Archived status is not configured")
        item.STATUS_ID = archived.STATUS_ID
        await self.session.commit()
