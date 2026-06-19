from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserResponse, UserLogin, TokenResponse
from app.services.user_service import authenticate_user, create_user, get_user_by_email
from app.core.security import create_access_token
from app.core.dependencies import get_current_admin
from app.db.database import get_db

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, credentials.email, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o password non corretti"
        )

    token = create_access_token(data={"sub": user.email})
    return TokenResponse(access_token=token)


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db), _: object = Depends(get_current_admin)):
    if get_user_by_email(db, user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email già registrata"
        )
    return create_user(db, user)

@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_admin)):
    # ✅ utile per il frontend per verificare chi è loggato
    return current_user