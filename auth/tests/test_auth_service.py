from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from auth.models import User, Session, db  # используем существующие модели


def _setup_in_memory_db():
    engine = create_engine("sqlite:///:memory:")
    db.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_auth_service__new_user__creates_user_and_session():
    s = _setup_in_memory_db()
    google_id = "gid123"
    email = "u@example.com"
    name = "User"
    device_id = "dev1"
    access_token = "tkn"
    expires_in = 86400

    # Импорт ожидаемой функции (пока отсутствует -> RED)
    from auth.services.auth_service import authenticate_google_payload

    result = authenticate_google_payload(
        db_session=s,
        google_id=google_id,
        email=email,
        name=name,
        device_id=device_id,
        access_token=access_token,
        expires_in_seconds=expires_in,
    )

    assert result == {
        "accessToken": access_token,
        "expiredIn": expires_in,
        "user": {
            "id": 1,
            "email": email,
            "name": name,
        },
    }

    # Проверка факта создания в БД
    user = s.query(User).filter_by(google_id=google_id).first()
    assert user is not None
    assert user.email == email
    sess = s.query(Session).filter_by(user_id=user.id).first()
    assert sess is not None

