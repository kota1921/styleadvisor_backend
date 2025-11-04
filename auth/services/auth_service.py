from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Optional, Dict, Any

from auth.models import User
from auth.services.session_service import upsert_session


def _hash_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def authenticate_google_payload(
    db_session,
    google_id: str,
    email: str,
    name: Optional[str],
    device_id: str,
    access_token: str,
    expires_in_seconds: int,
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    user = db_session.query(User).filter_by(google_id=google_id).first()
    if not user:
        user = User(
            google_id=google_id,
            device_id=device_id,
            email=email,
            name=name,
            last_login=now,
        )
        db_session.add(user)
        db_session.flush()
    else:
        user.last_login = now

    expires_at = now + timedelta(seconds=expires_in_seconds)
    access_token_hash = _hash_token(access_token)
    session_obj = upsert_session(
        db_session=db_session,
        user_id=user.id,
        device_id=device_id,
        access_token_hash=access_token_hash,
        expires_at=expires_at,
    )
    db_session.add(session_obj)
    db_session.commit()

    return {
        "accessToken": access_token,
        "expiredIn": expires_in_seconds,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
        },
    }
