import uuid
from types import SimpleNamespace

import pytest

from backend.core.security import decode_access_token
from backend.services.auth_service import (
    AuthConflictError,
    AuthService,
    AuthUnauthorizedError,
    AuthValidationError,
)
from backend.schemas.auth_schema import ChangePasswordIn, LoginIn, RegisterIn


class FakeAuthRepo:
    def __init__(self):
        self.users_by_email = {}
        self.users_by_id = {}

    def get_user_by_email(self, email: str):
        return self.users_by_email.get(email)

    def get_user_by_id(self, user_id: uuid.UUID):
        return self.users_by_id.get(user_id)

    def create_user(
        self,
        email: str,
        password_hash: str,
        role: str = "student",
        first_name: str | None = None,
        last_name: str | None = None,
        display_name: str | None = None,
    ):
        user = SimpleNamespace(
            id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            role=role,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            is_active=True,
        )
        self.users_by_email[user.email] = user
        self.users_by_id[user.id] = user
        return user

    def update_password(self, user_id: uuid.UUID, password_hash: str):
        user = self.users_by_id.get(user_id)
        if user:
            user.password_hash = password_hash


def test_register_success():
    repo = FakeAuthRepo()
    service = AuthService(repo)

    out = service.register(RegisterIn(email="student@example.com", password="password123", role="student"))

    assert out.email == "student@example.com"
    assert out.role == "student"
    assert repo.get_user_by_email("student@example.com") is not None


def test_register_accepts_identity_fields():
    repo = FakeAuthRepo()
    service = AuthService(repo)

    out = service.register(
        RegisterIn(
            email="student@example.com",
            password="password123",
            role="student",
            first_name="Olasquare",
            last_name="Ola",
        )
    )
    user = repo.get_user_by_email("student@example.com")

    assert out.first_name == "Olasquare"
    assert out.last_name == "Ola"
    assert out.display_name == "Olasquare Ola"
    assert user.display_name == "Olasquare Ola"


def test_register_duplicate_email_fails():
    repo = FakeAuthRepo()
    service = AuthService(repo)

    service.register(RegisterIn(email="student@example.com", password="password123", role="student"))

    with pytest.raises(AuthConflictError):
        service.register(RegisterIn(email="student@example.com", password="password123", role="student"))


def test_login_invalid_password_fails():
    repo = FakeAuthRepo()
    service = AuthService(repo)

    service.register(RegisterIn(email="student@example.com", password="password123", role="student"))

    with pytest.raises(AuthUnauthorizedError):
        service.login(LoginIn(email="student@example.com", password="wrongpass"))


def test_change_password_success():
    repo = FakeAuthRepo()
    service = AuthService(repo)

    out = service.register(RegisterIn(email="student@example.com", password="password123", role="student"))
    user = repo.get_user_by_email("student@example.com")

    service.change_password(
        user.id,
        ChangePasswordIn(current_password="password123", new_password="newpassword123"),
    )

    login = service.login(LoginIn(email="student@example.com", password="newpassword123"))

    assert login.user_id == str(user.id)
    assert login.role == "student"
    assert login.first_name is None
    assert out.user_id == str(user.id)


def test_change_password_same_value_fails():
    repo = FakeAuthRepo()
    service = AuthService(repo)

    service.register(RegisterIn(email="student@example.com", password="password123", role="student"))
    user = repo.get_user_by_email("student@example.com")

    with pytest.raises(AuthValidationError):
        service.change_password(
            user.id,
            ChangePasswordIn(current_password="password123", new_password="password123"),
        )


def test_login_token_contains_user_and_student_id_claims():
    repo = FakeAuthRepo()
    service = AuthService(repo)

    service.register(RegisterIn(email="claims@example.com", password="password123", role="student"))
    user = repo.get_user_by_email("claims@example.com")

    login = service.login(LoginIn(email="claims@example.com", password="password123"))
    payload = decode_access_token(login.access_token)

    assert payload["sub"] == "claims@example.com"
    assert payload["role"] == "student"
    assert payload["user_id"] == str(user.id)
    assert payload["student_id"] == str(user.id)
