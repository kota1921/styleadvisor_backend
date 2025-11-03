import pytest
import requests


def test_verify_google_token__valid_token__returns_payload(monkeypatch):
    class DummyResp:
        status_code = 200
        def json(self):
            return {"sub": "gid123", "email": "u@example.com", "name": "User"}
    def fake_get(url):
        return DummyResp()
    monkeypatch.setattr(requests, "get", fake_get)
    from auth.google_verifier import verify_google_token
    payload = verify_google_token("stub_token")
    assert payload == {"google_id": "gid123", "email": "u@example.com", "name": "User"}


def test_verify_google_token__invalid_status__raises_value_error(monkeypatch):
    class DummyResp:
        status_code = 400
        def json(self):
            return {}
    def fake_get(url):
        return DummyResp()
    monkeypatch.setattr(requests, "get", fake_get)
    from auth.google_verifier import verify_google_token
    with pytest.raises(ValueError) as e:
        verify_google_token("bad_token")
    assert str(e.value) == "google token invalid"


def test_verify_google_token__missing_claims__raises_value_error(monkeypatch):
    class DummyResp:
        status_code = 200
        def json(self):
            return {"email": "u@example.com"}
    def fake_get(url):
        return DummyResp()
    monkeypatch.setattr(requests, "get", fake_get)
    from auth.google_verifier import verify_google_token
    with pytest.raises(ValueError) as e:
        verify_google_token("stub_token")
    assert str(e.value) == "missing required claims"


def test_verify_google_token__network_error__raises_value_error(monkeypatch):
    def fake_get(url):
        raise requests.RequestException("boom")
    monkeypatch.setattr(requests, "get", fake_get)
    from auth.google_verifier import verify_google_token
    with pytest.raises(ValueError) as e:
        verify_google_token("stub_token")
    assert str(e.value).startswith("network error:")
