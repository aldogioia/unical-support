from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.api.jwt_handler import decode_and_validate_access_token
from app.services.blacklist_service import is_token_blacklisted
from app.db.database import get_db

bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
):
    exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token non valido o scaduto",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token_str = credentials.credentials
    if is_token_blacklisted(db, token_str):
        raise exc
        
    payload = decode_and_validate_access_token(token_str)
    if not payload:
        raise exc

    email: str = payload.get("sub")
    if not email:
        raise exc

    from app.models.user import User

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.is_active:
        raise exc

    return user