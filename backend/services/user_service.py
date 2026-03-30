from uuid import UUID

from fastapi import HTTPException, status

from backend.repositories.user_repo import UserRepository
from backend.schemas.user_schema import UserProfileOut, UserProfileUpdateIn


class UserService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    @staticmethod
    def _normalize_optional_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def _to_profile_out(user) -> UserProfileOut:
        return UserProfileOut(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            first_name=user.first_name,
            last_name=user.last_name,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            phone=user.phone,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def get_me(self, user_id: UUID) -> UserProfileOut:
        user = self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
        return self._to_profile_out(user)

    def update_me(self, user_id: UUID, payload: UserProfileUpdateIn) -> UserProfileOut:
        user = self.repo.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

        raw_updates = payload.model_dump(exclude_unset=True)
        updates: dict[str, str | None] = {}
        for field_name in ["first_name", "last_name", "display_name", "avatar_url", "phone"]:
            if field_name in raw_updates:
                updates[field_name] = self._normalize_optional_text(raw_updates[field_name])

        if not updates:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No profile fields provided.")

        if "display_name" not in updates:
            first = updates.get("first_name", user.first_name)
            last = updates.get("last_name", user.last_name)
            joined = " ".join(part for part in [first, last] if part)
            if joined:
                updates["display_name"] = joined

        updated_user = self.repo.update_profile_fields(user, updates)
        return self._to_profile_out(updated_user)
