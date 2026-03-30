"""Auth schemas (register/login)."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Literal["student", "teacher", "admin"] = "student"
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str | None = Field(default=None, min_length=1, max_length=150)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)



# Add this alongside LoginIn and RegisterIn
class GoogleLoginIn(BaseModel):
    token: str
    
class AuthOut(BaseModel):
    access_token: str
    user_id: str
    role: str
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None


class RegisterOut(BaseModel):
    user_id: str
    email: EmailStr
    role: str
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
    message: str


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class MessageOut(BaseModel):
    message: str
