from firebase_functions import https_fn
import json
import logging
from tools.jwt_validator import validate_jwt

SECRET = "test"
logger = logging.getLogger("auth")


def _extract_token(req: https_fn.Request) -> str | None:
    try:
        if hasattr(req, 'get_json'):
            body = req.get_json(silent=True)  # type: ignore
        else:
            raw = getattr(req, 'data', b'')
            if isinstance(raw, (bytes, bytearray)):
                raw = raw.decode('utf-8')
            body = json.loads(raw) if raw else None
    except Exception as e:  # более широкий перехват, чтобы не ронять 500
        logger.warning("bad body parse: %s", e)
        body = None
    if isinstance(body, dict):
        token = body.get('token')
        if isinstance(token, str):
            token = token.strip()
            if token:
                return token
    return None


def get_access_token(req: https_fn.Request) -> https_fn.Response:
    if req.method.upper() != "POST":
        return https_fn.Response(json.dumps({"isValid": False, "token": None, "error": "method not allowed"}), status=405, headers={"Content-Type": "application/json"})

    try:
        token = _extract_token(req)
    except Exception as e:  # на случай неожиданных форматов
        logger.error("extract error: %s", e)
        return https_fn.Response(json.dumps({"isValid": False, "token": None, "error": "bad request"}), status=400, headers={"Content-Type": "application/json"})

    if not token:
        return https_fn.Response(json.dumps({"isValid": False, "token": None, "error": "missing token"}), status=400, headers={"Content-Type": "application/json"})

    try:
        validate_jwt(token, SECRET)
        body = {"isValid": True, "token": token}
        return https_fn.Response(json.dumps(body), status=200, headers={"Content-Type": "application/json"})
    except ValueError as e:
        logger.info("validation failed: %s", e)
        body = {"isValid": False, "token": token, "error": str(e)}
        return https_fn.Response(json.dumps(body), status=400, headers={"Content-Type": "application/json"})
    except Exception as e:  # чтобы не получить 500 в ответ
        logger.error("unexpected validation error: %s", e)
        body = {"isValid": False, "token": token, "error": "internal validation error"}
        return https_fn.Response(json.dumps(body), status=400, headers={"Content-Type": "application/json"})
