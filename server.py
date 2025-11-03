from datetime import datetime, timedelta, timezone
from tools.logger_config import TimedFileLoggerConfigurator

from flask import request, jsonify, Flask
from flask_jwt_extended import JWTManager, create_access_token

from auth.google_verifier import verify_google_token
from auth.models import User, Session
from base_response import BaseResponse
from db import db

app = Flask(__name__)

# Настройки
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['JWT_SECRET_KEY'] = 'super_secret_key'  # замени в проде на переменную окружения
db.init_app(app)
jwt = JWTManager(app)

TimedFileLoggerConfigurator().configure(app)

with app.app_context():
    db.create_all()


@app.route('/auth/google', methods=['POST'])
def google_auth():
    app.logger.info('Попытка входа через Google OAuth')
    data = request.get_json()
    google_token = data.get("authToken")
    device_id = data.get("deviceId")

    if not google_token or not device_id:
        app.logger.warning('Не переданы токен или device_id')
        return jsonify({"error": "Missing credentials"}), 400

    try:
        payload = verify_google_token(google_token)
    except ValueError as e:
        msg = str(e)
        if msg.startswith("network error"):
            app.logger.error('Сетевая ошибка при верификации Google токена')
            return jsonify({"error": "Upstream error"}), 502
        app.logger.warning('Google токен невалиден')
        return jsonify({"error": "Missing credentials"}), 401

    google_id = payload.get("google_id")
    email = payload.get("email")
    name = payload.get("name")

    user = User.query.filter_by(google_id=google_id).first()
    if not user:
        app.logger.info(f'Создание нового пользователя: {email}')
        user = User(google_id=google_id, device_id=device_id, email=email, name=name, last_login=datetime.now(timezone.utc))
        db.session.add(user)
        db.session.commit()
    else:
        app.logger.info(f'Пользователь найден: {email}, обновление времени входа')
        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

    access_token = create_access_token(identity=google_id, expires_delta=timedelta(days=1))
    session = Session(
        user_id=user.id,
        access_token=access_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        device_info=device_id
    )
    db.session.add(session)
    db.session.commit()

    app.logger.info(f'Успешная аутентификация пользователя: {email}')

    return jsonify(
        BaseResponse(
            status_code=200,
            data={
                "accessToken": access_token,
                "expiredIn": 86400,
                "user": {
                    "id": user.id,
                    "email": email,
                    "name": name
                }
            }
        ).to_dict()
    ), 200


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
