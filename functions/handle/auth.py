from firebase_functions import https_fn
import json
import logging
from tools.jwt_validator import validate_jwt

SECRET = "test"
logger = logging.getLogger("auth")


def _extract_token(req: https_fn.Request) -> str | None:
    try:
        raw = getattr(req, 'data', b'') or b''
        if isinstance(raw, (bytes, bytearray)):
            raw_text = raw.decode('utf-8', errors='strict') if raw else ''
        else:
            raw_text = str(raw)
        body = json.loads(raw_text) if raw_text else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        logger.warning("bad body parse: %s", e)
        return None
    token = body.get('token') if isinstance(body, dict) else None
    if isinstance(token, str):
        token = token.strip()
        if token:
            return token
    return None


@https_fn.on_request()
def validate_token(req: https_fn.Request) -> https_fn.Response:
    if req.method.upper() != "POST":
        return https_fn.Response(json.dumps({"isValid": False, "token": None, "error": "method not allowed"}), status=405,
                                 headers={"Content-Type": "application/json"})
    token = _extract_token(req)
    if not token:
        return https_fn.Response(json.dumps({"isValid": False, "token": None, "error": "missing token"}), status=400,
                                 headers={"Content-Type": "application/json"})
    try:
        validate_jwt(token, SECRET)
        return https_fn.Response(json.dumps({"isValid": True, "token": token}), status=200,
                                 headers={"Content-Type": "application/json"})
    except ValueError as e:
        return https_fn.Response(json.dumps({"isValid": False, "token": token, "error": str(e)}), status=400,
                                 headers={"Content-Type": "application/json"})
    except Exception:
        logger.exception("unexpected error")
        return https_fn.Response(json.dumps({"isValid": False, "token": token, "error": "internal error"}), status=500,
                                 headers={"Content-Type": "application/json"})
