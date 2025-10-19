from firebase_functions import https_fn


def isPostRequest(request: https_fn.Request) -> bool:
    return request.method.upper() == 'POST'
