from firebase_functions import https_fn

def ok(data: Any = None, extra: Dict[str, Any] | None = None, status: int = 200) -> https_fn.Response:
    body: Dict[str, Any] = {"ok": True}
    if data is not None:
        body["data"] = data
    if extra:
        body.update(extra)
    return HttpResponse(status=status, body=body).to_response()

def error(status: int, code: str, message: str) -> https_fn.Response:
    return HttpResponse(status=status, body={"ok": False, "error": {"code": code, "message": message}}).to_response()

def method_not_allowed(method: str) -> https_fn.Response:
    return error(405, "method_not_allowed", f"Method {method} not allowed")

def bad_request(message: str = "bad request") -> https_fn.Response:
    return error(400, "bad_request", message)

def internal_error() -> https_fn.Response:
    return error(500, "internal_error", "Internal server error")

def endpoint(allowed_methods: Iterable[str] | None = None) -> Callable[[Callable[[https_fn.Request], Any]], Callable[[https_fn.Request], https_fn.Response]]:
    methods_set = {m.upper() for m in allowed_methods} if allowed_methods else None
    def decorate(fn: Callable[[https_fn.Request], Any]) -> Callable[[https_fn.Request], https_fn.Response]:
        def wrapper(req: https_fn.Request) -> https_fn.Response:
            try:
                if methods_set and req.method.upper() not in methods_set:
                    return method_not_allowed(req.method)
                result = fn(req)
                if isinstance(result, https_fn.Response):
                    return result
                if isinstance(result, HttpResponse):
                    return result.to_response()
                if isinstance(result, dict):
                    return HttpResponse(status=200, body=result).to_response()
                return ok(result)
            except HttpError as he:
                return error(he.status, he.code, he.message)
            except Exception as e:
                logger.exception("Unhandled endpoint error: %s", e)
                return internal_error()
        return wrapper
    return decorate
