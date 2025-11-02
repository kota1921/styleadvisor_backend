import jwt
from typing import Dict, Any

def validate_jwt(token: str, secret: str) -> Dict[str, Any]:
    if not token:
        raise ValueError("token пустой")
    if not secret:
        raise ValueError("secret пустой")
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise ValueError("token expired")
    except jwt.InvalidSignatureError:
        raise ValueError("invalid signature")
    except jwt.DecodeError:
        raise ValueError("invalid token")
    for key in ("userId", "iat", "exp"):
        if key not in payload:
            raise ValueError(f"missing claim {key}")
    try:
        iat = int(payload["iat"])
        exp = int(payload["exp"])
    except (ValueError, TypeError):
        raise ValueError("iat/exp должны быть int")
    if exp <= iat:
        raise ValueError("exp должно быть > iat")
    return payload
