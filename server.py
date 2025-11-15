from tools.logger_config import TimedFileLoggerConfigurator

from flask import request, jsonify, Flask
from flask_jwt_extended import JWTManager, create_access_token
from werkzeug.exceptions import HTTPException

from auth.services.google_auth_service import process_google_auth
from auth.exceptions import MissingCredentialsError, InvalidTokenError, UpstreamError
from auth.services.session_service import revoke_session, get_session_by_hash, revoke_session_by_hash
from auth.models import User
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
    if isinstance(e, HTTPException):
        return e
    app.logger.exception(f"unexpected error: {type(e).__name__}")
    return jsonify({"error": "Internal server error"}), 500


with app.app_context():
    db.create_all()


@app.route('/')
def index():
    return jsonify({
        "service": "FitMind API",
        "status": "running",
        "endpoints": {
            "auth": "/auth/google (POST)",
            "logout": "/auth/logout (POST)",
            "health": "/__nginx_alive"
        }
    }), 200


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
        # Логируем факт логина (без email для избегания PII):
        user_id = payload.get("user", {}).get("id")
        google_id = payload.get("user", {}).get("email")  # если нужно заменить на отдельное поле google_id
        app.logger.info(f"login user_id={user_id} email={google_id}")
        return jsonify(BaseResponse(status_code=status, data=payload).to_dict()), status
    except MissingCredentialsError:
        return jsonify({"error": "Missing credentials"}), 400
    except InvalidTokenError:
        return jsonify({"error": "Missing credentials"}), 401
    except UpstreamError:
        return jsonify({"error": "Upstream error"}), 502


@app.route('/auth/logout', methods=['POST'])
def logout():
    token_hash = request.headers.get("X-Access-Token", "").strip()
    if not token_hash:
        return jsonify({"error": "Missing token"}), 400
    session_obj = get_session_by_hash(db.session, token_hash)
    if not session_obj:
        return jsonify({"error": "Session not found"}), 404
    if session_obj.revoked:
        return jsonify({"error": "Session already revoked"}), 400
    success = revoke_session_by_hash(db.session, token_hash)
    if not success:
        return jsonify({"error": "Unable to revoke"}), 500
    db.session.commit()
    app.logger.info(f"logout user_id={session_obj.user_id} session_id={session_obj.id}")
    return jsonify(BaseResponse(status_code=200, data={"message": "logged out"}).to_dict()), 200


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
