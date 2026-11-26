"""Flask application factory and application instance.

Provides the Flask application factory, initializes application-wide
extensions and configuration, and registers the main route blueprint.

Article management, JSON parsing, configuration, and logging are
implemented in separate modules.
"""
from flask import Flask
from flask_wtf.csrf import CSRFProtect

from . import config
from .routes import main


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["SECRET_KEY"] = config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

    config.configure_file_logging()

    _ = CSRFProtect(app)

    config.ARTICLE_PATH.mkdir(parents=True, exist_ok=True)

    app.register_blueprint(main)

    return app


app = create_app()
