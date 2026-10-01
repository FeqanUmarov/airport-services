from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import AdminUser, CurrentUser, DatabaseSession, EditorUser
from app.modules.runways.schemas import (
    AreaCreate, AreaResponse, AreaUpdate, DirectionCreate, DirectionResponse,
    DirectionUpdate, RunwayCreate, RunwayListResponse, RunwayResponse,
    ClearwayGenerateRequest, RunwayUpdate, StatusUpdate, StripGenerateRequest, StripResponse, StripUpsert,
)
from app.modules.runways.service import (
    RunwayConflictError, RunwayNotFoundError, RunwayService, RunwayValidationError,
)


router = APIRouter(tags=["runways"])


def api_error(exc: ValueError) -> HTTPException:
    code = status.HTTP_404_NOT_FOUND if isinstance(exc, RunwayNotFoundError) else status.HTTP_409_CONFLICT if isinstance(exc, RunwayConflictError) else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(exc))


def geometry_changes(payload: Any) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    for key in ("geom", "centerline_geom", "threshold_geom"):
        if values.get(key) is not None and hasattr(values[key], "model_dump"):
            values[key] = values[key].model_dump()
    return values


@router.get("/airports/{air_id}/runways", response_model=RunwayListResponse)
async def list_runways(air_id: int, current: CurrentUser, session: DatabaseSession, search: str | None = Query(default=None, min_length=1), status_id: int | None = Query(default=None, gt=0)) -> RunwayListResponse:
    del current
    try: return await RunwayService(session).list_runways(air_id, search, status_id)
    except RunwayNotFoundError as exc: raise api_error(exc) from exc


@router.post("/airports/{air_id}/runways", response_model=RunwayResponse, status_code=201)
async def create_runway(air_id: int, payload: RunwayCreate, editor: EditorUser, session: DatabaseSession) -> RunwayResponse:
    del editor
    try: return await RunwayService(session).create_runway(air_id, payload)
    except (RunwayNotFoundError, RunwayConflictError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.get("/runways/{run_id}", response_model=RunwayResponse)
async def get_runway(run_id: int, current: CurrentUser, session: DatabaseSession) -> RunwayResponse:
    del current
    try: return await RunwayService(session).get_runway(run_id)
    except RunwayNotFoundError as exc: raise api_error(exc) from exc


@router.patch("/runways/{run_id}", response_model=RunwayResponse)
async def update_runway(run_id: int, payload: RunwayUpdate, editor: EditorUser, session: DatabaseSession) -> RunwayResponse:
    del editor
    try: return await RunwayService(session).update_runway(run_id, geometry_changes(payload))
    except (RunwayNotFoundError, RunwayConflictError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.patch("/runways/{run_id}/status", status_code=204)
async def runway_status(run_id: int, payload: StatusUpdate, editor: EditorUser, session: DatabaseSession) -> Response:
    del editor
    try: await RunwayService(session).set_status("runway", run_id, payload.status_id)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc
    return Response(status_code=204)


@router.delete("/runways/{run_id}", status_code=204)
async def archive_runway(run_id: int, admin: AdminUser, session: DatabaseSession) -> Response:
    del admin
    try: await RunwayService(session).archive("runway", run_id)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc
    return Response(status_code=204)


@router.get("/runways/{run_id}/directions", response_model=list[DirectionResponse])
async def list_directions(run_id: int, current: CurrentUser, session: DatabaseSession):
    del current
    try: return await RunwayService(session).list_directions(run_id)
    except RunwayNotFoundError as exc: raise api_error(exc) from exc


@router.post("/runways/{run_id}/directions", response_model=DirectionResponse, status_code=201)
async def create_direction(run_id: int, payload: DirectionCreate, editor: EditorUser, session: DatabaseSession):
    del editor
    try: return await RunwayService(session).create_direction(run_id, payload)
    except (RunwayNotFoundError, RunwayConflictError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.post("/runways/{run_id}/directions/regenerate", response_model=list[DirectionResponse])
async def regenerate_directions(run_id: int, editor: EditorUser, session: DatabaseSession):
    del editor
    try: return await RunwayService(session).regenerate_directions(run_id)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.get("/runway-directions/{direction_id}", response_model=DirectionResponse)
async def get_direction(direction_id: int, current: CurrentUser, session: DatabaseSession):
    del current
    try: return await RunwayService(session).get_direction(direction_id)
    except RunwayNotFoundError as exc: raise api_error(exc) from exc


@router.patch("/runway-directions/{direction_id}", response_model=DirectionResponse)
async def update_direction(direction_id: int, payload: DirectionUpdate, editor: EditorUser, session: DatabaseSession):
    del editor
    try: return await RunwayService(session).update_direction(direction_id, geometry_changes(payload))
    except (RunwayNotFoundError, RunwayConflictError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.patch("/runway-directions/{direction_id}/status", status_code=204)
async def direction_status(direction_id: int, payload: StatusUpdate, editor: EditorUser, session: DatabaseSession) -> Response:
    del editor
    try: await RunwayService(session).set_status("direction", direction_id, payload.status_id)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc
    return Response(status_code=204)


@router.delete("/runway-directions/{direction_id}", status_code=204)
async def archive_direction(direction_id: int, admin: AdminUser, session: DatabaseSession) -> Response:
    del admin
    try: await RunwayService(session).archive("direction", direction_id)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc
    return Response(status_code=204)


@router.get("/runways/{run_id}/strip", response_model=StripResponse)
async def get_strip(run_id: int, current: CurrentUser, session: DatabaseSession):
    del current
    try: return await RunwayService(session).get_strip(run_id)
    except RunwayNotFoundError as exc: raise api_error(exc) from exc


@router.put("/runways/{run_id}/strip", response_model=StripResponse)
async def upsert_strip(run_id: int, payload: StripUpsert, editor: EditorUser, session: DatabaseSession):
    del editor
    try: return await RunwayService(session).upsert_strip(run_id, payload)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.post("/runways/{run_id}/strip/generate", response_model=StripResponse)
async def generate_strip(run_id: int, payload: StripGenerateRequest, editor: EditorUser, session: DatabaseSession):
    del editor
    try: return await RunwayService(session).generate_strip(run_id, payload)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.patch("/runways/{run_id}/strip/status", status_code=204)
async def strip_status(run_id: int, payload: StatusUpdate, editor: EditorUser, session: DatabaseSession) -> Response:
    del editor
    try: await RunwayService(session).set_strip_status(run_id, payload.status_id)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc
    return Response(status_code=204)


@router.delete("/runways/{run_id}/strip", status_code=204)
async def archive_strip(run_id: int, admin: AdminUser, session: DatabaseSession) -> Response:
    del admin
    try: await RunwayService(session).archive_strip(run_id)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc
    return Response(status_code=204)


@router.get("/runway-directions/{direction_id}/areas", response_model=list[AreaResponse])
async def list_areas(direction_id: int, current: CurrentUser, session: DatabaseSession):
    del current
    try: return await RunwayService(session).list_areas(direction_id)
    except RunwayNotFoundError as exc: raise api_error(exc) from exc


@router.post("/runway-directions/{direction_id}/areas", response_model=AreaResponse, status_code=201)
async def create_area(direction_id: int, payload: AreaCreate, editor: EditorUser, session: DatabaseSession):
    del editor
    try: return await RunwayService(session).create_area(direction_id, payload)
    except (RunwayNotFoundError, RunwayConflictError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.post("/runway-directions/{direction_id}/areas/regenerate-clearway", response_model=AreaResponse)
async def regenerate_clearway(direction_id: int, payload: ClearwayGenerateRequest, editor: EditorUser, session: DatabaseSession):
    del editor
    try: return await RunwayService(session).regenerate_clearway(direction_id, payload)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.get("/runway-areas/{area_id}", response_model=AreaResponse)
async def get_area(area_id: int, current: CurrentUser, session: DatabaseSession):
    del current
    try: return await RunwayService(session).get_area(area_id)
    except RunwayNotFoundError as exc: raise api_error(exc) from exc


@router.patch("/runway-areas/{area_id}", response_model=AreaResponse)
async def update_area(area_id: int, payload: AreaUpdate, editor: EditorUser, session: DatabaseSession):
    del editor
    try: return await RunwayService(session).update_area(area_id, geometry_changes(payload))
    except (RunwayNotFoundError, RunwayConflictError, RunwayValidationError) as exc: raise api_error(exc) from exc


@router.patch("/runway-areas/{area_id}/status", status_code=204)
async def area_status(area_id: int, payload: StatusUpdate, editor: EditorUser, session: DatabaseSession) -> Response:
    del editor
    try: await RunwayService(session).set_status("area", area_id, payload.status_id)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc
    return Response(status_code=204)


@router.delete("/runway-areas/{area_id}", status_code=204)
async def archive_area(area_id: int, admin: AdminUser, session: DatabaseSession) -> Response:
    del admin
    try: await RunwayService(session).archive("area", area_id)
    except (RunwayNotFoundError, RunwayValidationError) as exc: raise api_error(exc) from exc
    return Response(status_code=204)
