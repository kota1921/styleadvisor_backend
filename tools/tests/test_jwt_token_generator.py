import time
import json
import hmac
import hashlib
import base64
import uuid
import pytest

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
    header = json.loads(_b64url_decode(parts[0]))
    payload = json.loads(_b64url_decode(parts[1]))
    assert header == {"alg": "HS256", "typ": "JWT"}
    assert payload["userId"] == user_id
    now = int(time.time())
    assert now - 5 <= payload["iat"] <= now + 5
    assert payload["exp"] - payload["iat"] == 300
    signing_input = '.'.join(parts[:2]).encode()
    expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    sig = _b64url_decode(parts[2])
    assert sig == expected_sig


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
    fixed = 1730486400
    gen = JwtTokenGenerator(now_provider=lambda: fixed)
    user_id = str(uuid.uuid4())
    secret = "test_secret"
    token = gen.generate(user_id, secret)
    parts = token.split('.')
    payload = json.loads(_b64url_decode(parts[1]))
    assert payload["iat"] == fixed
    assert payload["exp"] == fixed + 300


def test_generate_token_invalid_ttl():
    gen = JwtTokenGenerator()
    with pytest.raises(ValueError):
        gen.generate("user123", "secret", ttl_seconds=0)
# tools package root
