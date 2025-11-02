# tools модуль

Минимальные утилиты JWT:
- `generate_jwt(userId, secret, ttl_seconds=300, now_provider=time.time)` — генерация HS256 токена.
- `validate_jwt(token, secret)` — проверка подписи и базовых claim (userId, iat, exp).

Тесты: `tools/tests/`.

Правила:
- Только HS256.
- Нет сторонних stateful классов.
- Ошибки через ValueError (простые сообщения).

