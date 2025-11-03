from __future__ import annotations

from typing import Tuple
from datetime import timedelta

from auth.google_verifier import verify_google_token
from auth.services.auth_service import authenticate_google_payload
from auth.exceptions import MissingCredentialsError, InvalidTokenError, UpstreamError


def process_google_auth(db_session, auth_token: str | None, device_id: str | None, access_token_factory, ttl_seconds: int) -> Tuple[int, dict]:
    """Оркестрация входа через Google.

    Контракт:
        Вход:
            db_session: активная сессия БД (SQLAlchemy Session).
            auth_token: Google id_token от клиента (может быть None).
            device_id: идентификатор устройства (может быть None).
            access_token_factory: callable для генерации JWT (совместим с create_access_token).
            ttl_seconds: время жизни access token в секундах.
        Валидация:
            - Если auth_token или device_id отсутствуют -> MissingCredentialsError.
            - verify_google_token выполняет сетевой вызов и может бросить ValueError с
              сообщениями: "network error..." или ошибки структуры -> трансформируются
              в UpstreamError / InvalidTokenError.
        Исключения:
            MissingCredentialsError: не переданы требуемые поля.
            InvalidTokenError: токен не прошёл проверку (формат / подпись / claims).
            UpstreamError: сетевой сбой обращения к Google.
        Поведение:
            - Находит или создаёт пользователя, обновляет last_login.
            - Создаёт сессию (Session) с access_token.
        Возврат:
            (status_code, payload_dict)
            status_code: int (сейчас всегда 200, зарезервировано под будущие ветки).
            payload_dict: { accessToken, expiredIn, user: { id, email, name } }.
    """
    if not auth_token or not device_id:
        raise MissingCredentialsError("missing credentials")
    try:
        payload = verify_google_token(auth_token)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("network error"):
            raise UpstreamError("upstream error") from e
        raise InvalidTokenError("invalid token") from e

    google_id = payload.get("google_id")
    email = payload.get("email")
    name = payload.get("name")

    access_token = access_token_factory(identity=google_id, expires_delta=timedelta(seconds=ttl_seconds))
    result = authenticate_google_payload(
        db_session=db_session,
        google_id=google_id,
        email=email,
        name=name,
        device_id=device_id,
        access_token=access_token,
        expires_in_seconds=ttl_seconds,
    )
    return 200, result
