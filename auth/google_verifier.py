import requests


def verify_google_token(id_token: str) -> dict:
    if not id_token:
        raise ValueError("empty id_token")
    url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
    try:
        resp = requests.get(url)
    except requests.RequestException as e:
        raise ValueError(f"network error: {e}") from e
    if resp.status_code != 200:
        raise ValueError("google token invalid")
    data = resp.json()
    if not data.get("sub") or not data.get("email"):
        raise ValueError("missing required claims")
    return {
        "google_id": data.get("sub"),
        "email": data.get("email"),
        "name": data.get("name"),
    }
