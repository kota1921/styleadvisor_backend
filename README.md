# Firebase Functions (Python) + OpenAI

Этот проект показывает, как безопасно использовать ключ OpenAI в Python Cloud Functions для Firebase.

## Хранение ключа в Firebase (секрет)
Никогда не коммитьте реальный ключ (`sk-...`) в репозиторий.

1. Установите ключ как секрет (один раз / при ротации):
```bash
firebase functions:secrets:set OPENAI_API_KEY
```
Вставьте значение ключа при запросе (оно не сохранится в истории shell).

2. Задеплойте функции (секрет подтянется автоматически):
```bash
firebase deploy --only functions
```

3. При выполнении функции среда исполнения предоставит переменную окружения `OPENAI_API_KEY`.

4. Ротация (замена ключа):
```bash
firebase functions:secrets:set OPENAI_API_KEY
firebase deploy --only functions
```

## Локальная разработка
Есть два варианта:

### Вариант A: Экспорт переменной
```bash
export OPENAI_API_KEY="sk-proj-..."
```

### Вариант B: Файл `.env`
Создайте файл `.env` (он уже исключён из git через `.gitignore`):
```
OPENAI_API_KEY=sk-proj-...
```
Модуль `python-dotenv` автоматически загрузит его при старте (см. `main.py`).

## Код инициализации
В `main.py` ключ читается так:
```python
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)
```
Если переменная не найдена — выбрасывается ошибка (fail-fast), чтобы не пропустить неправильную конфигурацию.

## Вызов функции
После деплоя URL будет вида:
```
https://<REGION>-<PROJECT_ID>.cloudfunctions.net/on_request_example?text=Привет
```
Проверьте через curl:
```bash
curl "https://<REGION>-<PROJECT_ID>.cloudfunctions.net/on_request_example?text=Hello"
```

## Смена модели
Сейчас используется `gpt-4o-mini`. Замените на доступную в вашем аккаунте модель:
```python
response = client.responses.create(
    model="gpt-4o-mini",
    input=original,
)
```

## Обработка ответа
Ответ SDK сериализуется в JSON с учётом наличия `to_dict()` / `model_dump()`.

## Безопасность
- Не вставляйте ключ напрямую в код или README.
- Ограничьте права членов проекта Firebase.
- Регулярно ротируйте ключ, если он когда-либо раскрывался.
- Можно добавить квоты и мониторинг в OpenAI Dashboard.

## Возможные улучшения (Next steps)
- Добавить ограничение длины входного текста.
- Логирование (structured) без утечки PII и ключей.
- Юнит-тесты (mock OpenAI клиента).
- Rate limiting / кеш.
- Обработка таймаутов и повторов.

## Быстрый чеклист
- [x] Ключ хранится как секрет / переменная окружения
- [x] Локальная поддержка `.env`
- [x] Исключён `.env` из git
- [x] Добавлен `python-dotenv`

---
Если нужно — могу добавить пример тестов или утилиту для безопасной ротации ключа.

