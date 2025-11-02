import pytest
import uuid
import time
import jwt

from tools.jwt_token_generator import generate_jwt
from tools.jwt_validator import validate_jwt


def test_validate_ok():
    secret = "v_secret"
    device_id = str(uuid.uuid4())
    token = generate_jwt(device_id, secret, ttl_seconds=60)
    payload = validate_jwt(token, secret)
    assert payload["deviceId"] == device_id
    assert payload["exp"] - payload["iat"] == 60


def test_validate_expired_token():
    secret = "v_secret"
    past_now = lambda: time.time() - 120  # exp будет в прошлом
    token = generate_jwt("u1", secret, ttl_seconds=60, now_provider=past_now)
    with pytest.raises(ValueError) as e:
        validate_jwt(token, secret)
    assert "expired" in str(e.value)


def test_validate_invalid_signature():
    token = generate_jwt("u2", "secretA", ttl_seconds=30)
    with pytest.raises(ValueError) as e:
        validate_jwt(token, "secretB")
    assert "invalid signature" in str(e.value)


def test_validate_missing_claim():
    secret = "v_secret"
    now = int(time.time())
    # Без deviceId
    payload = {"iat": now, "exp": now + 60}
    token = jwt.encode(payload, secret, algorithm="HS256", headers={"typ": "JWT"})
    with pytest.raises(ValueError) as e:
        validate_jwt(token, secret)
    assert "missing claim deviceId" == str(e.value)


def test_validate_empty_token():
    with pytest.raises(ValueError) as e:
        validate_jwt("", "s")
    assert "token пустой" == str(e.value)


def test_validate_exp_le_iat():
    secret = "v_secret"
    now = int(time.time())
    payload = {"deviceId": "d3", "iat": now, "exp": now}  # exp == iat
    token = jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(ValueError) as e:
        validate_jwt(token, secret)
    assert "expired" in str(e.value)
