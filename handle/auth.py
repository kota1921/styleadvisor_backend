from firebase_functions import https_fn


def get_access_token(req: https_fn.Request) -> https_fn.Response:
    return https_fn.Response("echo", status=200)
