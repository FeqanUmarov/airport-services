from fastapi import APIRouter, HTTPException, Response, status

from app.core.dependencies import AdminUser, CurrentUser, DatabaseSession, EditorUser
from app.modules.declared_distances.schemas import (
    DeclaredDistanceResponse,
    DeclaredDistanceStatusUpdate,
    DeclaredDistanceUpsert,
)
from app.modules.declared_distances.service import (
    DeclaredDistanceNotFoundError,
    DeclaredDistanceService,
    DeclaredDistanceValidationError,
)


router = APIRouter(tags=["declared-distances"])


def api_error(exc: ValueError) -> HTTPException:
    code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc, DeclaredDistanceNotFoundError)
        else status.HTTP_400_BAD_REQUEST
    )
    return HTTPException(status_code=code, detail=str(exc))


@router.get(
    "/runway-directions/{direction_id}/declared-distances",
    response_model=DeclaredDistanceResponse,
)
async def get_declared_distances(
    direction_id: int,
    current: CurrentUser,
    session: DatabaseSession,
) -> DeclaredDistanceResponse:
    del current
    try:
        return await DeclaredDistanceService(session).get(direction_id)
    except DeclaredDistanceNotFoundError as exc:
        raise api_error(exc) from exc


@router.put(
    "/runway-directions/{direction_id}/declared-distances",
    response_model=DeclaredDistanceResponse,
)
async def upsert_declared_distances(
    direction_id: int,
    payload: DeclaredDistanceUpsert,
    editor: EditorUser,
    session: DatabaseSession,
) -> DeclaredDistanceResponse:
    del editor
    try:
        return await DeclaredDistanceService(session).upsert(direction_id, payload)
    except (DeclaredDistanceNotFoundError, DeclaredDistanceValidationError) as exc:
        raise api_error(exc) from exc


@router.patch(
    "/runway-directions/{direction_id}/declared-distances/status",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_declared_distances_status(
    direction_id: int,
    payload: DeclaredDistanceStatusUpdate,
    editor: EditorUser,
    session: DatabaseSession,
) -> Response:
    del editor
    try:
        await DeclaredDistanceService(session).update_status(
            direction_id,
            payload.status_id,
        )
    except (DeclaredDistanceNotFoundError, DeclaredDistanceValidationError) as exc:
        raise api_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/runway-directions/{direction_id}/declared-distances",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def archive_declared_distances(
    direction_id: int,
    admin: AdminUser,
    session: DatabaseSession,
) -> Response:
    del admin
    try:
        await DeclaredDistanceService(session).archive(direction_id)
    except (DeclaredDistanceNotFoundError, DeclaredDistanceValidationError) as exc:
        raise api_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
