import logging.config
import os
from functools import wraps
from typing import Tuple, Union

from flask import Blueprint, Response, g, jsonify, render_template, request
from logger_helper.logger_helper import LOGGING_CONFIG
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from src.models import User
from src.services import (
    create_tweet,
    delete_tweet,
    follow_user,
    get_timeline,
    get_user_by_id,
    like_tweet,
    unfollow_user,
    unlike_tweet,
    upload_media,
)

logging.config.dictConfig(LOGGING_CONFIG)
logger = logging.getLogger("routes")

bp = Blueprint("main_bp", __name__)

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif"}


def allowed_file(filename: str) -> bool:
    """
    Проверяет, имеет ли файл разрешённое расширение.

    :param filename: Имя файла.
    :return: True, если расширение разрешено, иначе False.
    """
    if "." not in filename:
        return False
    extension = filename.rsplit(".", 1)[1].lower()
    return extension in ALLOWED_EXTENSIONS


def require_api_key(f):
    """
    Декоратор для проверки наличия и валидности API ключа в заголовках запроса.

    Если ключ валиден, сохраняет пользователя в g.current_user.

    :param f: Функция-обработчик.
    :return: Обернутая функция с проверкой API ключа.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs) -> Union[Response, Tuple[Response, int]]:
        api_key = request.headers.get("api-key")
        if not api_key:
            return jsonify({"error": "API key missing"}), 401

        user = User.query.filter_by(api_key=api_key).first()
        if not user:
            return jsonify({"error": "Invalid API key"}), 403

        g.current_user = user
        return f(*args, **kwargs)

    return decorated_function


@bp.route("/", methods=["GET"])
def index() -> str:
    """
    Отдаёт главную HTML страницу.

    :return: Рендер шаблона "index.html".
    """
    return render_template("index.html")


@bp.route("/api/tweets", methods=["POST"])
@require_api_key
def create_tweet_route() -> Union[Response, Tuple[Response, int]]:
    """
    Создаёт новый твит текущего пользователя.

    Ожидает JSON с полями:
    - tweet_data: строка с содержимым твита (обязательно, максимум 280 символов)
    - tweet_media_ids: список ID медиа (опционально)

    :return: JSON с результатом и ID твита при успехе, либо ошибку.
    """
    data = request.json or {}
    tweet_data = data.get("tweet_data")
    tweet_media_ids = data.get("tweet_media_ids", [])

    if not tweet_data or not isinstance(tweet_data, str):
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "ValidationError",
                    "error_message": (
                        "Поле tweet_data обязательно и должно быть строкой"
                    ),
                }
            ),
            400,
        )

    if len(tweet_data) > 280:
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "ValidationError",
                    "error_message": "Длина твита не должна превышать 280 символов",
                }
            ),
            400,
        )

    if not isinstance(tweet_media_ids, list) or not all(
        isinstance(i, int) for i in tweet_media_ids
    ):
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "ValidationError",
                    "error_message": "tweet_media_ids должен быть списком целых чисел",
                }
            ),
            400,
        )

    success, tweet_id, error = create_tweet(g.current_user, tweet_data, tweet_media_ids)
    if success:
        return jsonify({"result": True, "tweet_id": tweet_id}), 201
    else:
        logger.error("Ошибка создания твита: %s", error)
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "ServerError",
                    "error_message": "Внутренняя ошибка сервера",
                }
            ),
            500,
        )


@bp.route("/api/medias", methods=["POST"])
@require_api_key
def upload_media_route() -> Union[Response, Tuple[Response, int]]:
    """
    Загружает медиа-файл от пользователя.

    Ожидает файл с ключом "file" в multipart/form-data.

    :return: JSON с результатом и ID загруженного медиа.
    """
    if "file" not in request.files:
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "ValidationError",
                    "error_message": "No file part in the request",
                }
            ),
            400,
        )

    file = request.files["file"]
    if file.filename == "":
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "ValidationError",
                    "error_message": "No selected file",
                }
            ),
            400,
        )

    if not allowed_file(file.filename):
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "ValidationError",
                    "error_message": "File type is not allowed",
                }
            ),
            400,
        )

    try:
        filename = secure_filename(file.filename)
        upload_folder = os.path.join("static", "uploads")
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)
    except SQLAlchemyError as e:
        logger.error("Ошибка при сохранении файла: %s", e, exc_info=True)
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "ServerError",
                    "error_message": "Ошибка при сохранении файла",
                }
            ),
            500,
        )

    success, media_id, error = upload_media(g.current_user, filename, file_path)
    if success:
        return jsonify({"result": True, "media_id": media_id}), 201
    else:
        logger.error("Ошибка сохранения медиа в БД: %s", error, exc_info=True)
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "ServerError",
                    "error_message": "Internal server error",
                }
            ),
            500,
        )


@bp.route("/api/tweets/<int:tweet_id>", methods=["DELETE"])
@require_api_key
def delete_tweet_route(tweet_id: int) -> Union[Response, Tuple[Response, int]]:
    """
    Удаляет твит текущего пользователя по ID.

    :param tweet_id: ID твита.
    :return: JSON с результатом успешного удаления или ошибкой.
    """
    success, error = delete_tweet(g.current_user, tweet_id)
    if success:
        return jsonify({"result": True})
    else:
        if error == "Твит не найден":
            return (
                jsonify(
                    {
                        "result": False,
                        "error_type": "NotFoundError",
                        "error_message": error,
                    }
                ),
                404,
            )
        elif error == "Удалять можно только свои твиты":
            return (
                jsonify(
                    {
                        "result": False,
                        "error_type": "PermissionError",
                        "error_message": error,
                    }
                ),
                403,
            )
        else:
            logger.error("Ошибка удаления твита: %s", error, exc_info=True)
            return (
                jsonify(
                    {
                        "result": False,
                        "error_type": "ServerError",
                        "error_message": "Ошибка сервера",
                    }
                ),
                500,
            )


def error_response(
    error_type: str, error_message: str, status_code: int = 400
) -> Tuple[Response, int]:
    """
    Формирует JSON-ответ с ошибкой и нужным HTTP статусом.
    """
    return (
        jsonify(
            {
                "result": False,
                "error_type": error_type,
                "error_message": error_message,
            }
        ),
        status_code,
    )


@bp.route("/api/tweets/<int:tweet_id>/likes", methods=["POST"])
@require_api_key
def like_tweet_route(tweet_id: int) -> Union[Response, Tuple[Response, int]]:
    """
    Ставит лайк текущего пользователя на твите.

    :param tweet_id: ID твита.
    :return: JSON с результатом.
    """
    success, error = like_tweet(g.current_user, tweet_id)
    if success:
        return jsonify({"result": True})

    if error == "Твит не найден":
        return error_response("NotFoundError", error, 404)

    logger.error("Ошибка лайка твита: %s", error, exc_info=True)
    return error_response("ServerError", "Ошибка сервера", 500)


@bp.route("/api/tweets/<int:tweet_id>/likes", methods=["DELETE"])
@require_api_key
def unlike_tweet_route(tweet_id: int) -> Union[Response, Tuple[Response, int]]:
    """
    Убирает лайк текущего пользователя с твита.

    :param tweet_id: ID твита.
    :return: JSON с результатом.
    """
    success, error = unlike_tweet(g.current_user, tweet_id)
    if success:
        return jsonify({"result": True})

    if error == "Твит не найден":
        return error_response("NotFoundError", error, 404)

    logger.error("Ошибка удаления лайка твита: %s", error, exc_info=True)
    return error_response("ServerError", "Ошибка сервера", 500)


@bp.route("/api/users/<int:user_id>/follow", methods=["POST"])
@require_api_key
def follow_user_route(user_id: int) -> Union[Response, Tuple[Response, int]]:
    """
    Подписывает текущего пользователя на другого пользователя по ID.

    :param user_id: ID пользователя для подписки.
    :return: JSON с результатом.
    """
    success, error = follow_user(g.current_user, user_id)
    if success:
        return jsonify({"result": True})
    else:
        if error == "Нельзя подписаться на себя":
            return (
                jsonify(
                    {
                        "result": False,
                        "error_type": "ValidationError",
                        "error_message": error,
                    }
                ),
                400,
            )
        elif error == "Пользователь не найден":
            return (
                jsonify(
                    {
                        "result": False,
                        "error_type": "NotFoundError",
                        "error_message": error,
                    }
                ),
                404,
            )
        else:
            logger.error("Ошибка подписки: %s", error, exc_info=True)
            return (
                jsonify(
                    {
                        "result": False,
                        "error_type": "ServerError",
                        "error_message": "Ошибка сервера",
                    }
                ),
                500,
            )


@bp.route("/api/users/<int:user_id>/follow", methods=["DELETE"])
@require_api_key
def unfollow_user_route(user_id: int) -> Union[Response, Tuple[Response, int]]:
    """
    Отписывает текущего пользователя от другого пользователя по ID.

    :param user_id: ID пользователя для отписки.
    :return: JSON с результатом.
    """
    success, error = unfollow_user(g.current_user, user_id)
    if success:
        return jsonify({"result": True})
    else:
        if error == "Пользователь не найден":
            return (
                jsonify(
                    {
                        "result": False,
                        "error_type": "NotFoundError",
                        "error_message": error,
                    }
                ),
                404,
            )
        else:
            logger.error("Ошибка отписки: %s", error, exc_info=True)
            return (
                jsonify(
                    {
                        "result": False,
                        "error_type": "ServerError",
                        "error_message": "Ошибка сервера",
                    }
                ),
                500,
            )


@bp.route("/api/tweets", methods=["GET"])
@require_api_key
def get_timeline_route() -> Union[Response, Tuple[Response, int]]:
    """
    Получает ленту твитов для текущего пользователя и тех, на кого он подписан.

    :return: JSON с твитами.
    """
    tweets = get_timeline(g.current_user)
    return jsonify({"result": True, "tweets": tweets})


def serialize_user(user: User) -> dict:
    """
    Сериализует данные пользователя в словарь.

    :param user: Объект пользователя.
    :return: Словарь с данными пользователя.
    """
    return {
        "id": user.id,
        "name": user.name,
        "followers": [{"id": u.id, "name": u.name} for u in user.followers],
        "following": [{"id": u.id, "name": u.name} for u in user.following],
    }


@bp.route("/api/users/me", methods=["GET"])
@require_api_key
def get_my_profile_route() -> Union[Response, Tuple[Response, int]]:
    """
    Получить профиль текущего пользователя.

    :return: JSON с данными пользователя.
    """
    user = g.current_user
    return jsonify({"result": True, "user": serialize_user(user)})


@bp.route("/api/users/<int:user_id>", methods=["GET"])
@require_api_key
def get_user_profile_route(user_id: int) -> Union[Response, Tuple[Response, int]]:
    """
    Получить профиль пользователя по ID.

    :param user_id: ID пользователя.
    :return: JSON с данными пользователя или ошибкой, если не найден.
    """
    user = get_user_by_id(user_id)
    if not user:
        return (
            jsonify(
                {
                    "result": False,
                    "error_type": "NotFoundError",
                    "error_message": "Пользователь не найден",
                }
            ),
            404,
        )

    return jsonify({"result": True, "user": serialize_user(user)})
