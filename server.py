from datetime import datetime, timedelta, timezone
from tools.logger_config import TimedFileLoggerConfigurator

from flask import request, jsonify, Flask
from flask_jwt_extended import JWTManager, create_access_token

from auth.services.google_auth_service import process_google_auth
from auth.exceptions import MissingCredentialsError, InvalidTokenError, UpstreamError
from auth.models import User, Session
from base_response import BaseResponse
from db import db

app = Flask(__name__)

ACCESS_TOKEN_TTL_SECONDS = 86400

# Настройки
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['JWT_SECRET_KEY'] = 'super_secret_key'  # замени в проде на переменную окружения
db.init_app(app)
jwt = JWTManager(app)

TimedFileLoggerConfigurator().configure(app)


@app.errorhandler(Exception)
def handle_unexpected_error(e):
    app.logger.error(f"unexpected error: {type(e).__name__}")
    return jsonify({"error": "Internal server error"}), 500


with app.app_context():
    db.create_all()


@app.route('/auth/google', methods=['POST'])
def google_auth():
    data = request.get_json(silent=True) or {}
    auth_token = data.get("authToken")
    device_id = data.get("deviceId")
    try:
        status, payload = process_google_auth(
            db_session=db.session,
            auth_token=auth_token,
            device_id=device_id,
            access_token_factory=create_access_token,
            ttl_seconds=ACCESS_TOKEN_TTL_SECONDS,
        )
        return jsonify(BaseResponse(status_code=status, data=payload).to_dict()), status
    except MissingCredentialsError:
        return jsonify({"error": "Missing credentials"}), 400
    except InvalidTokenError:
        return jsonify({"error": "Missing credentials"}), 401
    except UpstreamError:
        return jsonify({"error": "Upstream error"}), 502


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
