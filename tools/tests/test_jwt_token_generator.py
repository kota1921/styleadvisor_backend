import time
import json
import base64
import uuid
import pytest
import jwt

from tools.jwt_token_generator import JwtTokenGenerator


def _b64url_decode(segment: str) -> bytes:
    pad = '=' * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def test_generate_token_basic():
    gen = JwtTokenGenerator()
    user_id = str(uuid.uuid4())
    secret = "test_secret"
    token = gen.generate(user_id, secret)
    parts = token.split('.')
    assert len(parts) == 3
    header = jwt.get_unverified_header(token)
    assert header == {"alg": "HS256", "typ": "JWT"}
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    assert decoded["userId"] == user_id
    now = int(time.time())
    assert now - 5 <= decoded["iat"] <= now + 5
    assert decoded["exp"] - decoded["iat"] == 300


def test_generate_token_empty_user():
    gen = JwtTokenGenerator()
    with pytest.raises(ValueError):
        gen.generate("", "secret")


def test_generate_token_empty_secret():
    gen = JwtTokenGenerator()
    with pytest.raises(ValueError):
        gen.generate("user123", "")


def test_generate_token_custom_ttl():
    gen = JwtTokenGenerator()
    user_id = str(uuid.uuid4())
    secret = "test_secret"
    token = gen.generate(user_id, secret, ttl_seconds=120)
    parts = token.split('.')
    payload = json.loads(_b64url_decode(parts[1]))
    assert payload["exp"] - payload["iat"] == 120


def test_generate_token_fixed_time():
    fixed = int(time.time())  # актуальное время вместо устаревшего
    gen = JwtTokenGenerator(now_provider=lambda: fixed)
    user_id = str(uuid.uuid4())
    secret = "test_secret"
    token = gen.generate(user_id, secret)
    decoded = jwt.decode(token, secret, algorithms=["HS256"])
    assert decoded["iat"] == fixed
    assert decoded["exp"] == fixed + 300


def test_generate_token_invalid_ttl():
    gen = JwtTokenGenerator()
    with pytest.raises(ValueError):
        gen.generate("user123", "secret", ttl_seconds=0)
# tools package root
