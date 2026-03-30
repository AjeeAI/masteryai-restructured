import uuid

from sqlalchemy.orm import Session

from backend.models.user import User


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.query(User).filter(User.id == user_id).first()

    def update_profile_fields(self, user: User, updates: dict) -> User:
        for field_name, field_value in updates.items():
            setattr(user, field_name, field_value)

        self.db.commit()
        self.db.refresh(user)
        return user
