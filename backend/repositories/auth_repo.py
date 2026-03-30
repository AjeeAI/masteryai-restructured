import uuid

from sqlalchemy.orm import Session

from backend.models.user import User


class AuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.query(User).filter(User.email == email).first()

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def create_user(
        self,
        email: str,
        password_hash: str,
        role: str = "student",
        first_name: str | None = None,
        last_name: str | None = None,
        display_name: str | None = None,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            role=role,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_password(self, user_id: uuid.UUID, password_hash: str) -> None:
        user = self.get_user_by_id(user_id)
        if not user:
            return
        user.password_hash = password_hash
        self.db.commit()
