from datetime import datetime, timedelta, timezone
import jwt
from fastapi import HTTPException, status, Request
from app.core.config import settings
from app.models.user import User
from app.models.enumerators.enumerators import TokenType

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30 # 1 month

def _create_token(user: User, expires_delta: timedelta, token_type: TokenType) -> str:
    issued_at = datetime.now(timezone.utc).replace(microsecond=0)
    expiration = issued_at + expires_delta

    payload = {
        "sub": str(user.id),
        "iat": int(issued_at.timestamp()),
        "exp": int(expiration.timestamp()),
        "role": user.role.value,
        "type": token_type.value
    }

    try:
        encoded_jwt = jwt.encode(
            payload,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM
        )
        return encoded_jwt
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Errore durante la generazione del {token_type.value} token"
        )


def create_access_token(user: User) -> str:
    return _create_token(user, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES), TokenType.ACCESS)


def create_refresh_token(user: User) -> str:
    return _create_token(user, timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES), TokenType.REFRESH)



def _decode_and_validate_token(token: str, expected_type: TokenType) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Token di tipo {expected_type.value} non valido o scaduto",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token,settings.SECRET_KEY,algorithms=[settings.ALGORITHM])

        token_type = payload.get("type")
        username = payload.get("sub")
        if token_type != expected_type.value or username is None:
            raise credentials_exception

        return payload

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise credentials_exception


def decode_and_validate_access_token(token: str) -> dict:
    return _decode_and_validate_token(token, TokenType.ACCESS)


def decode_and_validate_refresh_token(token: str) -> dict:
    return _decode_and_validate_token(token, TokenType.REFRESH)

def get_expiration_time(token: str) -> int:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"verify_exp": False}
        )
        
        expiration = payload.get("exp")
        if expiration is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Il token non contiene un campo di scadenza (exp)"
            )
            
        return int(expiration)

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o firma corrotta",
            headers={"WWW-Authenticate": "Bearer"},
        )

def verify_token_format(token: str):
    
    try:
        jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token non valido o firma corrotta",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_access_token_from_request(request: Request) -> str:
    return _get_jwt_from_request(request, TokenType.ACCESS)

def get_refresh_token_from_request(request: Request) -> str:
    return _get_jwt_from_request(request, TokenType.REFRESH)

def _get_jwt_from_request(request: Request, token: TokenType) -> str:
    starts = ""
    header_name = ""

    if token == TokenType.ACCESS:
        header_name = "Authorization"
        starts = "Bearer "
    elif token == TokenType.REFRESH:
        header_name = "X-Refresh-Token"
        # starts rimane stringa vuota come nel codice Java

    header = request.headers.get(header_name)

    if header and header.startswith(starts):
        return header.replace(starts, "", 1)

    return "invalid"