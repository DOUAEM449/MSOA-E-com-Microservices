from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    name: str = Field(..., description="Full name, must not be blank.", examples=["Youssef"])
    email: str = Field(..., description="E-mail address, unique (case-insensitive).", examples=["youssef@example.com"])
    password: str = Field(..., description="Password, 1 to 72 bytes.", examples=["Secret123"])


class LoginRequest(BaseModel):
    email: str = Field(..., examples=["demo@msoa.shop"])
    password: str = Field(..., examples=["demo123"])


class UserResponse(BaseModel):
    id: str = Field(..., description="User identifier.", examples=["user-1"])
    name: str = Field(..., examples=["Demo Customer"])
    email: str = Field(..., examples=["demo@msoa.shop"])
    role: str = Field(..., description="CUSTOMER or ADMIN.", examples=["CUSTOMER"])


class LoginResponse(BaseModel):
    user: UserResponse
    token: str = Field(..., description="Opaque session token, sent back as `Authorization: Bearer <token>`.",
                       examples=["token-3f1c2a9e-8b7d-4c1e-9f0a-1234567890ab"])


class LogoutResponse(BaseModel):
    success: bool = Field(..., examples=[True])


class ErrorResponse(BaseModel):
    message: str = Field(..., description="Human-readable error message.", examples=["Invalid email or password."])
