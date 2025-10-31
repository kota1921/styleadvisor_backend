# Firebase Functions (Python) + OpenAI

Полные правила, гайд по секректам OpenAI и инструкции перенесены в `RULES.md`.

См.: [RULES.md](./RULES.md)

Кратко:
- Секрет OpenAI хранится через `firebase functions:secrets:set OPENAI_API_KEY`.
- Локально используем переменную окружения или `.env` (не коммитим).
- Деплой: `firebase deploy --only functions`.
- Пример вызова функции и остальные детали: в `RULES.md`.

Если нужно вернуть подробности обратно сюда — скажите.
