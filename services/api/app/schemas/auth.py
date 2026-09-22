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


class DistrictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str


class UserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=256)
    role: str = Field(pattern="^(operator|auditor)$")
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    district_ids: list[UUID] = Field(min_length=1)


class UserUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=256)
    role: Optional[str] = Field(default=None, pattern="^(operator|auditor)$")
    is_active: Optional[bool] = None
    district_ids: Optional[list[UUID]] = None


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
    districts: list[DistrictRead] = Field(default_factory=list)


class UserCreatedResponse(BaseModel):
    user: UserRead
    temporary_password: str


class MeResponse(UserRead):
    pass
