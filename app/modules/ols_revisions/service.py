import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.ols_revisions.repository import OlsRevisionRepository
from app.modules.ols_revisions.schemas import OlsRevisionResponse


class OlsRevisionNotFoundError(ValueError): pass


class OlsRevisionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session=session; self.repository=OlsRevisionRepository(session)

    @staticmethod
    def response(row: Any) -> OlsRevisionResponse:
        item=row[0]
        return OlsRevisionResponse(revision_id=item.REVISION_ID,ols_surface_id=item.OLS_SURFACE_ID,revision_no=item.REVISION_NO,standard_ols_id=item.STANDARD_OLS_ID,generation_method_id=item.GENERATION_METHOD_ID,air_id=item.AIR_ID,run_id=item.RUN_ID,run_dir_id=item.RUN_DIR_ID,aze_name=item.AZE_NAME,eng_name=item.ENG_NAME,geometry=json.loads(row.geojson),status_id=item.STATUS_ID,change_type=item.CHANGE_TYPE,change_note=item.CHANGE_NOTE,created_by=item.CREATED_BY,created_date=item.CREATED_DATE)

    async def list(self,surface_id:int) -> list[OlsRevisionResponse]:
        if await self.repository.surface(surface_id) is None: raise OlsRevisionNotFoundError("OLS surface does not exist")
        return [self.response(row) for row in await self.repository.list_rows(surface_id)]

    async def get(self,surface_id:int,revision_no:int) -> OlsRevisionResponse:
        row=await self.repository.get_row(surface_id,revision_no)
        if row is None: raise OlsRevisionNotFoundError("OLS surface revision does not exist")
        return self.response(row)

    async def restore(self,surface_id:int,revision_no:int,user_id:int,note:str|None) -> OlsRevisionResponse:
        surface=await self.repository.surface(surface_id); row=await self.repository.get_row(surface_id,revision_no)
        if surface is None: raise OlsRevisionNotFoundError("OLS surface does not exist")
        if row is None: raise OlsRevisionNotFoundError("OLS surface revision does not exist")
        revision=row[0]; surface.STANDARD_OLS_ID=revision.STANDARD_OLS_ID; surface.GENERATION_METHOD_ID=revision.GENERATION_METHOD_ID; surface.AIR_ID=revision.AIR_ID; surface.RUN_ID=revision.RUN_ID; surface.RUN_DIR_ID=revision.RUN_DIR_ID; surface.AZE_NAME=revision.AZE_NAME; surface.ENG_NAME=revision.ENG_NAME; surface.GEOM=revision.GEOM; surface.STATUS_ID=revision.STATUS_ID
        created=await self.repository.create_snapshot(surface,change_type="RESTORE",note=note or f"Restored revision {revision_no}",user_id=user_id); await self.session.commit()
        return await self.get(surface_id,created.REVISION_NO)
