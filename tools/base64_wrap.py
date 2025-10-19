import base64

def encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def decode(data: str) -> bytes:
    padding = '=' * (-len(data) % 4)  # Add necessary padding
    return base64.urlsafe_b64decode(data + padding)
