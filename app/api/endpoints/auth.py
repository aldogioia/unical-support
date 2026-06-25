from app.api.authorization import is_admin_user
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserResponse, UserLogin, TokenResponse
from app.api.authentication import get_current_user
from app.services.user_service import authenticate_user, create_user, get_user_by_email, refresh
from app.db.database import get_db

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    return authenticate_user(db, credentials.email, credentials.password)
    


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, db: Session = Depends(get_db), _: object = Depends(is_admin_user)): # todo remove admin control ?
    if get_user_by_email(db, user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email già registrata"
        )
    return create_user(db, user)

@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)):
    # utile per il frontend per verificare chi è loggato
    return current_user

@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    return refresh(db=db, refresh_token=refresh_token)