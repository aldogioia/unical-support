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


# ============================================================================
# ⚠️  SOLO SVILUPPO — BYPASS TEMPORANEO ⚠️
# TODO: rimuovere questa funzione (e ripristinare get_current_user) non
# appena il frontend avrà un vero flusso di login. Attualmente il frontend
# non invia mai un token, quindi get_current_user restituirebbe sempre 401
# su ogni azione di scrittura (upload documenti, creare categorie/template,
# salvare risposte). Questo bypass permette di continuare a sviluppare senza
# login: se un token valido è presente lo usa normalmente, altrimenti usa un
# utente "dev" fittizio invece di rifiutare la richiesta.
# ============================================================================

_optional_bearer_scheme = HTTPBearer(auto_error=False)

_DEV_BYPASS_EMAIL = "dev-bypass@local"


def _get_or_create_dev_bypass_user(db: Session):
    from app.models.user import User
    from app.models.enumerators.enumerators import UserRole

    user = db.query(User).filter(User.email == _DEV_BYPASS_EMAIL).first()
    if user is None:
        user = User(
            email=_DEV_BYPASS_EMAIL,
            hashed_password="",
            is_active=True,
            role=UserRole.admin,
        )
        user.apply_audit_fields(is_create=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_current_user_dev_bypass(
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer_scheme),
    db: Session = Depends(get_db),
):
    if credentials is not None:
        token_str = credentials.credentials
        if not is_token_blacklisted(db, token_str):
            payload = decode_and_validate_access_token(token_str)
            if payload:
                email = payload.get("sub")
                if email:
                    from app.models.user import User
                    user = db.query(User).filter(User.email == email).first()
                    if user and user.is_active:
                        return user
        # token presente ma non valido: non solleviamo eccezione, ricadiamo
        # comunque sull'utente dev per non bloccare lo sviluppo.

    return _get_or_create_dev_bypass_user(db)