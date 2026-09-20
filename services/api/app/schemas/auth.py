from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)


class UserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=256)
    role: str = Field(pattern="^(admin|operator|auditor)$")
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    role: Optional[str] = Field(default=None, pattern="^(admin|operator|auditor)$")
    is_active: Optional[bool] = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    display_name: str
    role: str
    is_active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None


class UserCreatedResponse(BaseModel):
    user: UserRead
    temporary_password: str


class MeResponse(UserRead):
    pass
