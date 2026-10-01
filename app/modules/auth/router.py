from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.dependencies import CurrentUser, DatabaseSession
from app.modules.auth.schemas import (
    ChangePasswordRequest,
    CurrentUserResponse,
    LogoutRequest,
    RefreshTokenRequest,
    TokenPair,
)
from app.modules.auth.service import AuthenticationError, AuthService


router = APIRouter(prefix="/auth", tags=["auth"])


def unauthorized(exc: AuthenticationError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=str(exc),
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/login", response_model=TokenPair)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: DatabaseSession,
) -> TokenPair:
    try:
        return await AuthService(session).login(form.username, form.password)
    except AuthenticationError as exc:
        raise unauthorized(exc) from exc


@router.post("/refresh", response_model=TokenPair)
async def refresh_token(
    payload: RefreshTokenRequest,
    session: DatabaseSession,
) -> TokenPair:
    try:
        return await AuthService(session).refresh(payload.refresh_token)
    except AuthenticationError as exc:
        raise unauthorized(exc) from exc


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: LogoutRequest, session: DatabaseSession) -> Response:
    try:
        await AuthService(session).logout(payload.refresh_token)
    except AuthenticationError as exc:
        raise unauthorized(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT)
async def logout_all(current: CurrentUser, session: DatabaseSession) -> Response:
    await AuthService(session).logout_all(current.user.USER_ID)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangePasswordRequest,
    current: CurrentUser,
    session: DatabaseSession,
) -> Response:
    try:
        await AuthService(session).change_password(
            current,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=CurrentUserResponse)
async def current_user(current: CurrentUser) -> CurrentUserResponse:
    return AuthService.to_current_user(current)
