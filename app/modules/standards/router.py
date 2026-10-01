from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import AdminUser, CurrentUser, DatabaseSession, EditorUser
from app.modules.standards.schemas import (
    StandardCreate,
    StandardListResponse,
    StandardResponse,
    StandardStatusUpdate,
    StandardUpdate,
    StandardParameterUpsert,
    StandardSurfaceCreate,
    StandardSurfaceListResponse,
    StandardSurfaceUpdate,
)
from app.modules.standards.service import (
    StandardConflictError,
    StandardNotFoundError,
    StandardService,
    StandardValidationError,
)


router = APIRouter(prefix="/standards", tags=["standards"])


def api_error(exc: ValueError) -> HTTPException:
    if isinstance(exc, StandardNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, StandardConflictError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(exc))


@router.get("", response_model=StandardListResponse)
async def list_standards(
    current: CurrentUser,
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=255),
    standard_type_id: int | None = Query(default=None, gt=0),
    status_id: int | None = Query(default=None, gt=0),
) -> StandardListResponse:
    del current
    return await StandardService(session).list_items(
        page=page,
        page_size=page_size,
        search=search,
        standard_type_id=standard_type_id,
        status_id=status_id,
    )


@router.post("", response_model=StandardResponse, status_code=status.HTTP_201_CREATED)
async def create_standard(
    payload: StandardCreate,
    editor: EditorUser,
    session: DatabaseSession,
) -> StandardResponse:
    del editor
    try:
        return await StandardService(session).create(payload)
    except (StandardConflictError, StandardValidationError) as exc:
        raise api_error(exc) from exc


@router.get("/{standard_id}", response_model=StandardResponse)
async def get_standard(
    standard_id: int,
    current: CurrentUser,
    session: DatabaseSession,
) -> StandardResponse:
    del current
    try:
        return await StandardService(session).get(standard_id)
    except StandardNotFoundError as exc:
        raise api_error(exc) from exc


@router.patch("/{standard_id}", response_model=StandardResponse)
async def update_standard(
    standard_id: int,
    payload: StandardUpdate,
    editor: EditorUser,
    session: DatabaseSession,
) -> StandardResponse:
    del editor
    try:
        return await StandardService(session).update(
            standard_id,
            payload.model_dump(exclude_unset=True),
        )
    except (StandardNotFoundError, StandardConflictError, StandardValidationError) as exc:
        raise api_error(exc) from exc


@router.patch("/{standard_id}/status", status_code=status.HTTP_204_NO_CONTENT)
async def update_standard_status(
    standard_id: int,
    payload: StandardStatusUpdate,
    editor: EditorUser,
    session: DatabaseSession,
) -> Response:
    del editor
    try:
        await StandardService(session).update_status(standard_id, payload.status_id)
    except (StandardNotFoundError, StandardValidationError) as exc:
        raise api_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete("/{standard_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_standard(
    standard_id: int,
    admin: AdminUser,
    session: DatabaseSession,
) -> Response:
    del admin
    try:
        await StandardService(session).archive(standard_id)
    except (StandardNotFoundError, StandardValidationError) as exc:
        raise api_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{standard_id}/ols-configurations", response_model=StandardSurfaceListResponse)
async def list_ols_configurations(standard_id: int, current: CurrentUser, session: DatabaseSession) -> StandardSurfaceListResponse:
    del current
    try:
        return await StandardService(session).list_surfaces(standard_id)
    except StandardNotFoundError as exc:
        raise api_error(exc) from exc


@router.post("/{standard_id}/ols-configurations", response_model=StandardSurfaceListResponse, status_code=status.HTTP_201_CREATED)
async def create_ols_configuration(standard_id: int, payload: StandardSurfaceCreate, editor: EditorUser, session: DatabaseSession) -> StandardSurfaceListResponse:
    del editor
    try:
        return await StandardService(session).create_surface(standard_id, payload)
    except (StandardNotFoundError, StandardConflictError, StandardValidationError) as exc:
        raise api_error(exc) from exc


@router.patch("/{standard_id}/ols-configurations/{standard_ols_id}", response_model=StandardSurfaceListResponse)
async def update_ols_configuration(standard_id: int, standard_ols_id: int, payload: StandardSurfaceUpdate, editor: EditorUser, session: DatabaseSession) -> StandardSurfaceListResponse:
    del editor
    try:
        return await StandardService(session).update_surface(standard_id, standard_ols_id, payload.model_dump(exclude_unset=True))
    except (StandardNotFoundError, StandardValidationError) as exc:
        raise api_error(exc) from exc


@router.delete("/{standard_id}/ols-configurations/{standard_ols_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_ols_configuration(standard_id: int, standard_ols_id: int, admin: AdminUser, session: DatabaseSession) -> Response:
    del admin
    try:
        await StandardService(session).archive_surface(standard_id, standard_ols_id)
    except (StandardNotFoundError, StandardValidationError) as exc:
        raise api_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{standard_id}/ols-configurations/{standard_ols_id}/parameters", response_model=StandardSurfaceListResponse)
async def upsert_ols_parameter(standard_id: int, standard_ols_id: int, payload: StandardParameterUpsert, editor: EditorUser, session: DatabaseSession) -> StandardSurfaceListResponse:
    del editor
    try:
        return await StandardService(session).upsert_parameter(standard_id, standard_ols_id, payload)
    except (StandardNotFoundError, StandardValidationError) as exc:
        raise api_error(exc) from exc


@router.delete("/{standard_id}/ols-configurations/{standard_ols_id}/parameters/{param_value_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_ols_parameter(standard_id: int, standard_ols_id: int, param_value_id: int, editor: EditorUser, session: DatabaseSession) -> Response:
    del editor
    try:
        await StandardService(session).archive_parameter(standard_id, standard_ols_id, param_value_id)
    except (StandardNotFoundError, StandardValidationError) as exc:
        raise api_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
