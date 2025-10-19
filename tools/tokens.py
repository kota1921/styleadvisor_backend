import hashlib
import hmac
import json
import base64
import time
from typing import Dict, Any

# Жёстко заданный тестовый секрет (заменить в проде)
_SERVER_SECRET = "b7d45c3d6a9f104f2f83e0c9b1a6d7f4e2c1a9b0f6d3e8c7a1f2b4d6e9c0a3f5"


def _b64url(raw: bytes) -> str:
    """URL-safe Base64 без паддинга."""
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def generate_access_token(device_id: str, ttl_seconds: int = 3600) -> str:
    """Минимальная генерация HMAC токена с iat/exp."""
    if not device_id:
        raise ValueError("device_id пустой")
    now = int(time.time())
    header: Dict[str, Any] = {"alg": "HS256", "typ": "JWT"}
    payload: Dict[str, Any] = {
        "device_id": device_id,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(_SERVER_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"
