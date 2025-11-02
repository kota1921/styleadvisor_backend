import time
from typing import Optional, Callable
import jwt


class JwtTokenGenerator:
    """Генератор JWT (HS256) на PyJWT."""

    def __init__(self, now_provider: Optional[Callable[[], float]] = None):
        self._now = now_provider or time.time

    def generate(self, user_id: str, secret: str, ttl_seconds: int = 300) -> str:
        if not user_id:
            raise ValueError("user_id пустой")
        if not secret:
            raise ValueError("secret пустой")
        if int(ttl_seconds) <= 0:
            raise ValueError("ttl_seconds должен быть > 0")
        now = int(self._now())
        payload = {
            "userId": user_id,
            "iat": now,
            "exp": now + int(ttl_seconds),
        }
        # typ добавим в headers (alg проставит библиотека)
        token = jwt.encode(payload, secret, algorithm="HS256", headers={"typ": "JWT"})
        # PyJWT>=2 возвращает строку
        return token
