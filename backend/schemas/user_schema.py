from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserProfileOut(BaseModel):
    user_id: str
    email: EmailStr
    role: str
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    phone: str | None = None
    created_at: datetime
    updated_at: datetime


class UserProfileUpdateIn(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str | None = Field(default=None, min_length=1, max_length=150)
    avatar_url: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=30)
