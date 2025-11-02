import jwt
from typing import Dict, Any
import hmac, hashlib, base64, time

# Допустимое расхождение часов (секунды)
_IAT_FUTURE_LEEWAY = 30

def _calc_sig(token: str, secret: str) -> str:
    try:
        header_payload, _sig = token.rsplit('.', 1)
    except ValueError:
        return ""
    digest = hmac.new(secret.encode(), header_payload.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip('=')


def validate_jwt(token: str, secret: str) -> Dict[str, Any]:
    if not token:
        raise ValueError("token пустой")
    if not secret:
        raise ValueError("secret пустой")
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            options={"verify_signature": True, "verify_exp": True, "verify_iat": False},
            leeway=_IAT_FUTURE_LEEWAY,
        )
    except jwt.ExpiredSignatureError as e:
        raise ValueError(str(e))
    except jwt.InvalidSignatureError:
        expected = _calc_sig(token, secret)
        raise ValueError(f"invalid signature (expected={expected})")
    except jwt.DecodeError as e:
        raise ValueError(f"decode error: {e}")
    except jwt.InvalidTokenError as e:
        raise ValueError(f"invalid token: {e}")
    for key in ("deviceId", "iat", "exp"):
        if key not in payload:
            raise ValueError(f"missing claim {key}")
    try:
        iat = int(payload["iat"])
        exp = int(payload["exp"])
    except (ValueError, TypeError):
        raise ValueError("iat/exp должны быть int")
    now = int(time.time())
    if iat - now > _IAT_FUTURE_LEEWAY:
        raise ValueError("iat слишком далеко в будущем")
    if exp <= iat:
        raise ValueError("exp должно быть > iat")
    return payload
