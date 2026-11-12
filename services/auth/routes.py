from fastapi import APIRouter, Header, status
from schemas import (
    ErrorResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RegisterRequest,
    UserResponse,
)
import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


def _error(description: str) -> dict:
    return {"model": ErrorResponse, "description": description}


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a customer account",
    responses={
        400: _error("Missing/blank field, invalid e-mail, or password longer than 72 bytes"),
        409: _error("E-mail already registered"),
    },
)
def register(req: RegisterRequest):
    return auth_service.register_user(req)


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Log in and receive a session token",
    responses={
        400: _error("Missing or blank e-mail/password"),
        401: _error("Invalid e-mail or password"),
    },
)
def login(req: LoginRequest):
    user_data, token = auth_service.authenticate_user(req)
    return {"user": user_data, "token": token}


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the user owning the session token",
    responses={401: _error("Missing, invalid or expired token")},
)
def get_current_user(authorization: str = Header(None), token: str = None):
    return auth_service.get_user_by_token(raw_authorization=authorization, token_param=token)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Invalidate the session token (idempotent)",
)
def logout(authorization: str = Header(None), token: str = None):
    return auth_service.logout_user(raw_authorization=authorization, token_param=token)
