from fastapi import APIRouter, HTTPException, Query, Response, status

from app.core.dependencies import AdminUser, DatabaseSession
from app.modules.users.schemas import (
    AdminPasswordReset,
    UserCreate,
    UserListResponse,
    UserResponse,
    UserRolesUpdate,
    UserStatusUpdate,
    UserUpdate,
)
from app.modules.users.service import (
    UserConflictError,
    UserNotFoundError,
    UserService,
    UserValidationError,
)


router = APIRouter(prefix="/users", tags=["users"])


def user_error(exc: ValueError) -> HTTPException:
    if isinstance(exc, UserNotFoundError):
        code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, UserConflictError):
        code = status.HTTP_409_CONFLICT
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=str(exc))


@router.get("", response_model=UserListResponse)
async def list_users(
    admin: AdminUser,
    session: DatabaseSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=255),
    status_id: int | None = Query(default=None, gt=0),
) -> UserListResponse:
    del admin
    return await UserService(session).list_users(
        page=page,
        page_size=page_size,
        search=search,
        status_id=status_id,
    )


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    admin: AdminUser,
    session: DatabaseSession,
) -> UserResponse:
    del admin
    try:
        return await UserService(session).create_user(payload)
    except (UserConflictError, UserValidationError) as exc:
        raise user_error(exc) from exc


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, admin: AdminUser, session: DatabaseSession) -> UserResponse:
    del admin
    try:
        return await UserService(session).get_user(user_id)
    except UserNotFoundError as exc:
        raise user_error(exc) from exc


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    admin: AdminUser,
    session: DatabaseSession,
) -> UserResponse:
    del admin
    try:
        return await UserService(session).update_user(
            user_id,
            payload.model_dump(exclude_unset=True),
        )
    except (UserNotFoundError, UserConflictError) as exc:
        raise user_error(exc) from exc


@router.patch("/{user_id}/status", response_model=UserResponse)
async def update_user_status(
    user_id: int,
    payload: UserStatusUpdate,
    admin: AdminUser,
    session: DatabaseSession,
) -> UserResponse:
    try:
        return await UserService(session).update_status(user_id, payload.status_id, admin)
    except (UserNotFoundError, UserValidationError) as exc:
        raise user_error(exc) from exc


@router.put("/{user_id}/roles", response_model=UserResponse)
async def replace_user_roles(
    user_id: int,
    payload: UserRolesUpdate,
    admin: AdminUser,
    session: DatabaseSession,
) -> UserResponse:
    try:
        return await UserService(session).replace_roles(user_id, payload.role_codes, admin)
    except (UserNotFoundError, UserValidationError) as exc:
        raise user_error(exc) from exc


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_user_password(
    user_id: int,
    payload: AdminPasswordReset,
    admin: AdminUser,
    session: DatabaseSession,
) -> Response:
    del admin
    try:
        await UserService(session).reset_password(user_id, payload.new_password)
    except UserNotFoundError as exc:
        raise user_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{user_id}/revoke-tokens", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_user_tokens(
    user_id: int,
    admin: AdminUser,
    session: DatabaseSession,
) -> Response:
    del admin
    try:
        await UserService(session).revoke_tokens(user_id)
    except UserNotFoundError as exc:
        raise user_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
