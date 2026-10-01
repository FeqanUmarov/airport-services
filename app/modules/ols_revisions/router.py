from fastapi import APIRouter, HTTPException

from app.core.dependencies import CurrentUser, DatabaseSession, EditorUser
from app.modules.ols_revisions.schemas import OlsRevisionResponse, OlsRevisionRestoreRequest
from app.modules.ols_revisions.service import OlsRevisionNotFoundError, OlsRevisionService


router=APIRouter(prefix="/ols-surfaces",tags=["ols-revisions"])


@router.get("/{surface_id}/revisions",response_model=list[OlsRevisionResponse])
async def list_revisions(surface_id:int,current:CurrentUser,session:DatabaseSession):
    del current
    try: return await OlsRevisionService(session).list(surface_id)
    except OlsRevisionNotFoundError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc


@router.get("/{surface_id}/revisions/{revision_no}",response_model=OlsRevisionResponse)
async def get_revision(surface_id:int,revision_no:int,current:CurrentUser,session:DatabaseSession):
    del current
    try: return await OlsRevisionService(session).get(surface_id,revision_no)
    except OlsRevisionNotFoundError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc


@router.post("/{surface_id}/revisions/{revision_no}/restore",response_model=OlsRevisionResponse)
async def restore_revision(surface_id:int,revision_no:int,payload:OlsRevisionRestoreRequest,editor:EditorUser,session:DatabaseSession):
    try: return await OlsRevisionService(session).restore(surface_id,revision_no,editor.user.USER_ID,payload.note)
    except OlsRevisionNotFoundError as exc: raise HTTPException(status_code=404,detail=str(exc)) from exc
