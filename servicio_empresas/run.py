import logging
import os
import sys

from config import app_config
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager

from api.api_key_management_routes import api_key_bp
from api.auth_api_routes import auth_bp
from api.menu_api_routes import menu_api_bp
from api.web_panel_menu_api_routes import web_menu_bp


def configure_logging():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)

    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)


configure_logging()
logger = logging.getLogger(__name__)


def create_and_configure_app():
    app_instance = Flask(__name__)
    app_instance.config["SECRET_KEY"] = app_config.SECRET_KEY
    app_instance.config["DEBUG"] = app_config.DEBUG
    app_instance.config["MONGO_URI"] = app_config.MONGO_URI
    app_instance.config["MONGO_DB_NAME"] = app_config.MONGO_DB_NAME
    app_instance.config["MONGO_MENUS_COLLECTION"] = app_config.MONGO_MENUS_COLLECTION
    app_instance.config["MONGO_USERS_COLLECTION"] = app_config.MONGO_USERS_COLLECTION
    app_instance.config["TEMP_UPLOADS_FOLDER"] = app_config.TEMP_UPLOADS_FOLDER
    app_instance.config["JWT_SECRET_KEY"] = app_config.JWT_SECRET_KEY

    JWTManager(app_instance)

    @app_instance.errorhandler(404)
    def resource_not_found(e):
        return jsonify(error=str(e)), 404

    @app_instance.errorhandler(500)
    def internal_server_error(e):
        return jsonify(error="Error interno del servidor"), 500

    if not os.path.exists(app_instance.config["TEMP_UPLOADS_FOLDER"]):
        try:
            os.makedirs(app_instance.config["TEMP_UPLOADS_FOLDER"])
        except OSError as e:
            logger.error(f"Error creando directorio de subidas temporales: {e}")

    app_instance.register_blueprint(auth_bp)
    app_instance.register_blueprint(api_key_bp)
    app_instance.register_blueprint(menu_api_bp)
    app_instance.register_blueprint(web_menu_bp)

    @app_instance.route("/health")
    def health_check():
        return jsonify(status="ok"), 200

    logger.info("Application initialized.")
    return app_instance


app = create_and_configure_app()

if __name__ == "__main__":
    PUERTO_SERVICIO_EMPRESAS = app_config.SERVICIO_EMPRESAS_PORT
    logger.info(f"Starting Servicio Empresas on port {PUERTO_SERVICIO_EMPRESAS}...")
    app.run(debug=app.config["DEBUG"], port=PUERTO_SERVICIO_EMPRESAS, host="0.0.0.0")
