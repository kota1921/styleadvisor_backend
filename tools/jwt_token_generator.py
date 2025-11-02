import time
import hmac
import hashlib
import json
import base64
from typing import Optional, Callable


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode('utf-8').rstrip('=')


class JwtTokenGenerator:
    """Генератор JWT (HS256)."""
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
        header = {"alg": "HS256", "typ": "JWT"}
        payload = {
            "userId": user_id,
            "iat": now,
            "exp": now + int(ttl_seconds),
        }
        header_b64 = _b64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))
        payload_b64 = _b64url(json.dumps(payload, separators=(',', ':')).encode('utf-8'))
        signing_input = f"{header_b64}.{payload_b64}".encode('utf-8')
        signature = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
        sig_b64 = _b64url(signature)
        return f"{header_b64}.{payload_b64}.{sig_b64}"
