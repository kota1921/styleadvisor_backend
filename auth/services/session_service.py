from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from auth.models import Session


def get_session_by_user_id(db_session, user_id: int) -> Optional[Session]:
    return db_session.query(Session).filter_by(user_id=user_id).first()


def upsert_session(
    db_session,
    user_id: int,
    device_id: str,
    access_token_hash: str,
    expires_at: datetime,
) -> Session:
    session_obj = get_session_by_user_id(db_session, user_id)
    if session_obj is None:
        session_obj = Session(
            user_id=user_id,
            access_token_hash=access_token_hash,
            expires_at=expires_at,
            device_info=device_id,
            revoked=False,
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(session_obj)
    else:
        session_obj.access_token_hash = access_token_hash
        session_obj.expires_at = expires_at
        session_obj.device_info = device_id
        session_obj.revoked = False  # сброс при новом логине
    return session_obj


def revoke_session(db_session, user_id: int) -> bool:
    session_obj = get_session_by_user_id(db_session, user_id)
    if not session_obj:
        return False
    session_obj.revoked = True
    return True


def get_session_by_hash(db_session, access_token_hash: str) -> Optional[Session]:
    return db_session.query(Session).filter_by(access_token_hash=access_token_hash).first()


def revoke_session_by_hash(db_session, access_token_hash: str) -> bool:
    session_obj = get_session_by_hash(db_session, access_token_hash)
    if not session_obj or session_obj.revoked:
        return False
    session_obj.revoked = True
    return True
