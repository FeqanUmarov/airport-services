from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import AdminUser, CurrentUser, DatabaseSession, EditorUser
from app.modules.airports.schemas import (
    AirportCreate,
    AirportListResponse,
    AirportResponse,
    AirportStatusUpdate,
    AirportUpdate,
)
from app.modules.airports.service import (
    AirportConflictError,
    AirportNotFoundError,
    AirportService,
    AirportValidationError,
)


router = APIRouter(prefix="/airports", tags=["airports"])


def airport_error(exc: ValueError) -> HTTPException:
    if isinstance(exc, AirportNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, AirportConflictError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(exc))


@router.get("", response_model=AirportListResponse)
async def list_airports(
    current: CurrentUser,
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=255),
    country_id: int | None = Query(default=None, gt=0),
    city_id: int | None = Query(default=None, gt=0),
    status_id: int | None = Query(default=None, gt=0),
) -> AirportListResponse:
    del current
    return await AirportService(session).list_airports(
        page=page,
        page_size=page_size,
        search=search,
        country_id=country_id,
        city_id=city_id,
        status_id=status_id,
    )


@router.post("", response_model=AirportResponse, status_code=status.HTTP_201_CREATED)
async def create_airport(
    payload: AirportCreate,
    editor: EditorUser,
    session: DatabaseSession,
) -> AirportResponse:
    del editor
    try:
        return await AirportService(session).create_airport(payload)
    except (AirportConflictError, AirportValidationError) as exc:
        raise airport_error(exc) from exc


@router.get("/{air_id}", response_model=AirportResponse)
async def get_airport(
    air_id: int,
    current: CurrentUser,
    session: DatabaseSession,
) -> AirportResponse:
    del current
    try:
        return await AirportService(session).get_airport(air_id)
    except AirportNotFoundError as exc:
        raise airport_error(exc) from exc


@router.patch("/{air_id}", response_model=AirportResponse)
async def update_airport(
    air_id: int,
    payload: AirportUpdate,
    editor: EditorUser,
    session: DatabaseSession,
) -> AirportResponse:
    del editor
    changes = payload.model_dump(exclude_unset=True)
    for geometry_field in ("arp_geom", "boundary_geom"):
        if changes.get(geometry_field) is not None:
            changes[geometry_field] = changes[geometry_field].model_dump()
    try:
        return await AirportService(session).update_airport(air_id, changes)
    except (AirportNotFoundError, AirportConflictError, AirportValidationError) as exc:
        raise airport_error(exc) from exc


@router.patch("/{air_id}/status", response_model=AirportResponse)
async def update_airport_status(
    air_id: int,
    payload: AirportStatusUpdate,
    editor: EditorUser,
    session: DatabaseSession,
) -> AirportResponse:
    del editor
    try:
        return await AirportService(session).update_status(air_id, payload.status_id)
    except (AirportNotFoundError, AirportValidationError) as exc:
        raise airport_error(exc) from exc


@router.delete("/{air_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_airport(
    air_id: int,
    admin: AdminUser,
    session: DatabaseSession,
) -> Response:
    del admin
    try:
        await AirportService(session).archive(air_id)
    except (AirportNotFoundError, AirportValidationError) as exc:
        raise airport_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
