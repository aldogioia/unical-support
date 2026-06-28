from uuid import UUID
from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
from app.schemas.user import TokenResponse
from app.api.jwt_handler import create_access_token, create_refresh_token, decode_and_validate_refresh_token
from app.api.password_handler import verify_dummy_password, verify_password, get_password_hash
from fastapi import HTTPException, status

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def create_user(db: Session, user: UserCreate, user_id: UUID):
    if get_user_by_email(db, user.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email già registrata"
        )
        
    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        role = user.role
    )
    db_user.apply_audit_fields(user_id=user_id, is_create=True)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def authenticate_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)

    unauthorized_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="email o password errati",
        headers={"WWW-Authenticate": "Bearer"},
    )

    inactive_user_exception = HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Utente non autorizzato",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not user:
        verify_dummy_password(password)
        raise unauthorized_exception
    if not verify_password(password, user.hashed_password):
        raise unauthorized_exception
    if not user.is_active:
        raise inactive_user_exception

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

def refresh(db: Session, refresh_token: str):
    payload = decode_and_validate_refresh_token(refresh_token)

    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Refresh token non valido")
        
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=401, detail="Utente non trovato")
        
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Utente non autorizzato o inattivo")
        
    new_access_token = create_access_token(user)
    new_refresh_token = create_refresh_token(user)
    return TokenResponse(access_token=new_access_token, refresh_token=new_refresh_token)