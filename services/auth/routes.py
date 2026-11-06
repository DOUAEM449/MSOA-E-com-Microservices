from fastapi import APIRouter, Header, status
from schemas import RegisterRequest, LoginRequest, UserResponse, LoginResponse
import auth_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(req: RegisterRequest):
    return auth_service.register_user(req)

@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest):
    user_data, token = auth_service.authenticate_user(req)
    return {
        "user": user_data,
        "token": token
    }

@router.get("/me", response_model=UserResponse)
def get_current_user(authorization: str = Header(None), token: str = None):
    return auth_service.get_user_by_token(raw_authorization=authorization, token_param=token)

@router.post("/logout")
def logout(authorization: str = Header(None), token: str = None):
    return auth_service.logout_user(raw_authorization=authorization, token_param=token)
