import logging.config
import os
import time

from flask import Flask
from flask_swagger_ui import get_swaggerui_blueprint
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from logger_helper.logger_helper import LOGGING_CONFIG
from src.models import db

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("main")

SWAGGER_URL = "/api/docs"
API_URL = "/static/swagger.yaml"


def wait_for_db(uri: str, retries: int = 10, delay: int = 3) -> None:
    """
    Пытается установить соединение с базой данных по указанной URI,
    повторяя попытки с задержкой, чтобы дождаться доступности БД.
    Args:
        uri (str): Строка подключения к базе данных.
        retries (int, optional): Количество попыток подключения.
        По умолчанию 10.
        delay (int, optional): Задержка между попытками в секундах.
        По умолчанию 3.

    Raises:
        RuntimeError: Если не удалось подключиться к базе после всех попыток.
    """
    engine = create_engine(uri)
    for i in range(retries):
        try:
            conn = engine.connect()
            conn.close()
            return
        except OperationalError:
            logger.info(
                "Попытка соединения %d/%d не удалась, ждем %d секунд...",
                i + 1,
                retries,
                delay,
            )
            time.sleep(delay)
    raise RuntimeError("Не удалось подключиться к базе за отведенное время")


def create_app() -> Flask:
    """
    Создает и конфигурирует Flask-приложение с подключением к базе данных
    и регистратором маршрутов.

    Возвращает:
        Flask: Созданный Flask-приложение.

    Raises:
        RuntimeError: Если переменная окружения DATABASE_URL не установлена или
                      если соединение с базой не может быть установлено.
    """
    application = Flask(
        __name__,
        static_folder="static",
        static_url_path="/",
        template_folder="templates",
    )

    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL не установлена")

    wait_for_db(database_url)

    logger.info("DATABASE_URL: %s", database_url)
    db_url = os.environ.get("DATABASE_URL")
    application.config["SQLALCHEMY_DATABASE_URI"] = db_url
    application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(application)

    from src.routes import bp

    application.register_blueprint(bp)
    with application.app_context():
        try:
            db.create_all()
            logger.info("База данных создана")
        except OperationalError as e:
            logger.error("Ошибка при создании таблиц: %s", e)

    swaggerui_blueprint = get_swaggerui_blueprint(
        SWAGGER_URL, API_URL, config={"app_name": "Корпоративный Твиттер API"}
    )

    application.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)

    return application


app = create_app()

if __name__ == "__main__":
    logger.info("Сервер запускается")
    app.run(host="0.0.0.0", debug=False)
