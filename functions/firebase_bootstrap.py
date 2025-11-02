from firebase_admin import initialize_app, get_app


def get_firebase_app():
    try:
        return get_app()
    except ValueError:
        return initialize_app()
