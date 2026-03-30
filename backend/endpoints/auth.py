"""Authentication and account security endpoints.

Public API for register/login/password update.
"""


import os

from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.database import get_db
from backend.repositories.auth_repo import AuthRepository
from backend.schemas.auth_schema import (
    AuthOut,
    ChangePasswordIn,
    LoginIn,
    GoogleLoginIn,
    MessageOut,
    RegisterIn,
    RegisterOut,
)
from backend.services.auth_service import (
    AuthConflictError,
    AuthService,
    AuthUnauthorizedError,
    AuthValidationError,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


def _service(db: Session) -> AuthService:
    return AuthService(AuthRepository(db))


@router.post("/register", response_model=RegisterOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    """Create a new platform user account.

    This endpoint is used by students/teachers/admins during sign-up.
    It enforces unique email and minimum password quality via the auth service.
    """
    try:
        return _service(db).register(payload)
    except AuthConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except AuthValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry.",
        )


@router.post("/login", response_model=AuthOut, status_code=status.HTTP_200_OK)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """Authenticate a user and issue a JWT access token.

    The response includes role and user identity fields required by frontend state.
    """
    try:
        return _service(db).login(payload)
    except AuthUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry.",
        )


@router.put("/password", response_model=MessageOut, status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordIn,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Change password for the currently authenticated user.

    Requires a valid bearer token and the current password for verification.
    """
    try:
        _service(db).change_password(current_user.id, payload)
        return MessageOut(message="Password changed successfully.")
    except AuthUnauthorizedError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))
    except AuthValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry.",
        )
        
        
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

@router.post("/google", response_model=AuthOut, status_code=status.HTTP_200_OK)
def google_login(payload: GoogleLoginIn, db: Session = Depends(get_db)):
    """Authenticate a user via Google OAuth and issue a JWT access token.
    
    Performs just-in-time registration if the Google email is not found.
    The response perfectly matches standard traditional login.
    """
    try:
        # 1. Verify the token with Google's servers
        id_info = id_token.verify_oauth2_token(
            id_token=payload.token,
            request=google_requests.Request(),
            audience=GOOGLE_CLIENT_ID
        )

        # 2. Extract user info
        email = id_info.get("email")
        first_name = id_info.get("given_name")
        last_name = id_info.get("family_name")
        display_name = id_info.get("name")

        # 3. Pass extracted data to the auth service
        # The service will handle checking the DB, creating the user if needed, 
        # and generating your platform's JWT access token.
        return _service(db).google_login(
            email=email,
            first_name=first_name,
            last_name=last_name,
            display_name=display_name
        )

    except ValueError:
        # If the token is fake, expired, or tampered with
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Invalid Google Token"
        )
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable. Please retry.",
        )
