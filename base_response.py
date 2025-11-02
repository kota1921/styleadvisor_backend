from typing import Any

class BaseResponse:
    def __init__(self, status_code: int, data: Any, error: str = ""):
        self.status_code = status_code
        self.data = data
        self.error = error

    def to_dict(self):
        return {
            "status_code": self.status_code,
            "data": self.data,
            "error": self.error
        }
