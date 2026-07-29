from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.blacklist import Blacklist
from app.api.jwt_handler import get_expiration_time, verify_token_format

def add_token_to_blacklist(db: Session, token_str: str) -> Blacklist:
    exp_timestamp = get_expiration_time(token_str)
    expires_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

    db_blacklist = Blacklist(
        token=token_str,
        expires_at=expires_datetime
    )
    
    db.add(db_blacklist)
    db.commit()
    db.refresh(db_blacklist)
    return db_blacklist


def is_token_blacklisted(db: Session, token_str: str) -> bool:
    if not token_str:
        return False
        
    verify_token_format(token_str)
    
    stmt = select(Blacklist).where(Blacklist.token == token_str)
    result = db.execute(stmt).scalar_one_or_none()
    
    return result is not None