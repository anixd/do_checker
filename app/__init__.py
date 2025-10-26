from flask import Flask
from config.loader import ConfigStore
from logging_.engine_logger import get_engine_logger
from dotenv import load_dotenv
import os

load_dotenv()

def create_app() -> Flask:
    app = Flask(__name__)
    app.config['JSONIFY_PRETTYPRINT_REGULAR'] = False

    app.secret_key = os.environ.get('SECRET_KEY')
    if not app.secret_key:
        print("WARNING: SECRET_KEY not set. Flash messages won't work.")
        app.secret_key = 'dev-secret-key'

    ConfigStore.init()
    get_engine_logger()

    from .routes import bp as routes_bp
    app.register_blueprint(routes_bp)

    # SSE endpoint
    from .sse import bp as sse_bp
    app.register_blueprint(sse_bp)

    return app
