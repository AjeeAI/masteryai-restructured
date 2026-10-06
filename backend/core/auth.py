from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from uuid import UUID

from backend.core.database import get_db
from backend.core.security import decode_access_token
from backend.repositories.auth_repo import AuthRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
):
    token = None
    if credentials:
        token = (credentials.credentials or "").strip().strip('"').strip("'")
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
    
    if not token:
        token = request.cookies.get("access_token")
        
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated.")

    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token.")

    repo = AuthRepository(db)
    user = None

    try:
        user_id_claim = payload.get("user_id") or payload.get("student_id")
        if user_id_claim:
            try:
                user = repo.get_user_by_id(UUID(str(user_id_claim)))
            except (TypeError, ValueError):
                user = None

        if user is None:
            subject = payload.get("sub")
            if subject:
                user = repo.get_user_by_email(subject)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry.",
        )

    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not authorized.")

    return user
