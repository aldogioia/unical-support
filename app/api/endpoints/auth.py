from typing import Optional
from typing import Annotated
from app.api.authorization import is_admin_user
from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserResponse, UserLogin, TokenResponse
from app.api.authentication import get_current_user
from app.services.user_service import authenticate_user, create_user, refresh, logout_user
from app.db.database import get_db
from app.models.user import User

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    return authenticate_user(db, credentials.email, credentials.password)
    


@router.post("/register", response_model=UserResponse)
def register(user: UserCreate, current_user: Annotated[User, Depends(is_admin_user)], db: Session = Depends(get_db)): # todo remove admin control ?
    return create_user(db, user, current_user.id)

@router.get("/me", response_model=UserResponse)
def me(current_user=Depends(get_current_user)):
    # utile per il frontend per verificare chi è loggato
    return current_user

@router.post("/refresh", response_model=TokenResponse)
def refresh_access_token(refresh_token: str, db: Session = Depends(get_db)):
    return refresh(db=db, refresh_token=refresh_token)

@router.post("/logout") 
def logout(
    authorization: Annotated[Optional[str], Header(alias="Authorization")] = None,
    x_refresh_token: Annotated[Optional[str], Header(alias="X-Refresh-Token")] = None,
    db: Session = Depends(get_db)
):
    # Pulisce l'header Authorization rimuovendo il prefisso "Bearer " se presente
    access_token = None
    if authorization and authorization.startswith("Bearer "):
        access_token = authorization.replace("Bearer ", "", 1)

    return logout_user(db=db, access_token=access_token, refresh_token=x_refresh_token)