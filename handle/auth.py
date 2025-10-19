import logging

from firebase_functions import https_fn

import firebase_bootstrap
from tools import tokens
from tools.request_type_verifier import isPostRequest

app = firebase_bootstrap.get_firebase_app()
logger = logging.getLogger("auth")

_DEVICE_ID_KEY = "device_id"


def get_access_token(req: https_fn.Request) -> https_fn.Response:
    if not isPostRequest(req):
        return https_fn.Response(f"Method not allowed {req.method.upper()} {isPostRequest(req)}", status=405)

    if _DEVICE_ID_KEY not in req.args:
        return https_fn.Response("Missing device_id parameter", status=400)
    device_id = req.args.get(_DEVICE_ID_KEY)
    token = tokens.generate_access_token(device_id)

    return https_fn.Response(token, status=200)
