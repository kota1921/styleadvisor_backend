import time
import jwt
from typing import Callable


def generate_jwt(user_id: str, secret: str, ttl_seconds: int = 300, now_provider: Callable[[], float] = time.time) -> str:
    if not user_id:
        raise ValueError("user_id пустой")
    if not secret:
        raise ValueError("secret пустой")
    if int(ttl_seconds) <= 0:
        raise ValueError("ttl_seconds должен быть > 0")
    now = int(now_provider())
    payload = {
        "userId": user_id,
        "iat": now,
        "exp": now + int(ttl_seconds),
    }
    return jwt.encode(payload, secret, algorithm="HS256", headers={"typ": "JWT"})
