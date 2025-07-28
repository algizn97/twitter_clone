import io
import pytest
import os
from src.routes import bp
from src.models import db, User, Tweet

@pytest.fixture
def app():
    from flask import Flask

    app = Flask(__name__, static_folder="static", template_folder=os.path.abspath("templates"))
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False

    from src.models import db as _db
    _db.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        _db.create_all()
        # Создаём тестового пользователя с known API key
        user = User(name="TestUser", api_key="test_api_key")
        _db.session.add(user)
        _db.session.commit()

    yield app

    # Очистка БД
    with app.app_context():
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def auth_headers(api_key="test_api_key"):
    return {"api-key": api_key}


def test_index(client):
    res = client.get("/")
    assert res.status_code == 200
    assert b"<html" in res.data


def test_create_tweet_success(client):
    data = {"tweet_data": "Hello world!"}
    res = client.post("/api/tweets", json=data, headers=auth_headers())
    assert res.status_code == 201
    resp_json = res.get_json()
    assert resp_json["result"] is True
    assert "tweet_id" in resp_json


def test_create_tweet_missing_data(client):
    res = client.post("/api/tweets", json={}, headers=auth_headers())
    assert res.status_code == 400
    resp_json = res.get_json()
    assert resp_json["result"] is False
    assert resp_json["error_type"] == "ValidationError"


def test_create_tweet_too_long(client):
    long_text = "a" * 281
    res = client.post("/api/tweets", json={"tweet_data": long_text}, headers=auth_headers())
    assert res.status_code == 400
    data = res.get_json()
    assert data["error_message"] == "Длина твита не должна превышать 280 символов"


def test_upload_media_success(client):
    data = {
        "file": (io.BytesIO(b"test image data"), "test.jpg"),
    }
    res = client.post("/api/medias", content_type="multipart/form-data", data=data, headers=auth_headers())
    assert res.status_code == 201
    resp_json = res.get_json()
    assert resp_json["result"] is True
    assert "media_id" in resp_json


def test_upload_media_invalid_filetype(client):
    data = {
        "file": (io.BytesIO(b"test data"), "test.txt"),
    }
    res = client.post("/api/medias", content_type="multipart/form-data", data=data, headers=auth_headers())
    assert res.status_code == 400
    assert "File type is not allowed" in res.get_data(as_text=True)


def test_delete_tweet(client, app):
    # Сначала создадим твит
    with app.app_context():
        user = User.query.filter_by(api_key="test_api_key").first()
        tweet = Tweet(content="Delete me", user_id=user.id)
        db.session.add(tweet)
        db.session.commit()
        tweet_id = tweet.id

    # Удаляем
    res = client.delete(f"/api/tweets/{tweet_id}", headers=auth_headers())
    assert res.status_code == 200
    resp_json = res.get_json()
    assert resp_json["result"] is True

    # Проверяем, что твит удалён
    with app.app_context():
        deleted = Tweet.query.get(tweet_id)
        assert deleted is None


def test_like_and_unlike_tweet(client, app):
    with app.app_context():
        user = User.query.filter_by(api_key="test_api_key").first()
        tweet = Tweet(content="Like me", user_id=user.id)
        db.session.add(tweet)
        db.session.commit()
        tweet_id = tweet.id

    # Лайкнуть твит
    res = client.post(f"/api/tweets/{tweet_id}/likes", headers=auth_headers())
    assert res.status_code == 200
    assert res.json["result"] is True

    # Попытаться лайкнуть снова (идемпотентно)
    res = client.post(f"/api/tweets/{tweet_id}/likes", headers=auth_headers())
    assert res.status_code == 200
    assert res.json["result"] is True

    # Убрать лайк
    res = client.delete(f"/api/tweets/{tweet_id}/likes", headers=auth_headers())
    assert res.status_code == 200
    assert res.json["result"] is True

    # Убрать лайк повторно (идемпотентно)
    res = client.delete(f"/api/tweets/{tweet_id}/likes", headers=auth_headers())
    assert res.status_code == 200
    assert res.json["result"] is True


def test_follow_and_unfollow_user(client, app):
    with app.app_context():
        current_user = User.query.filter_by(api_key="test_api_key").first()
        user_to_follow = User(name="OtherUser", api_key="other_key")
        db.session.add(user_to_follow)
        db.session.commit()
        user_to_follow_id = user_to_follow.id

    # Подписаться
    res = client.post(f"/api/users/{user_to_follow_id}/follow", headers=auth_headers())
    assert res.status_code == 200
    assert res.json["result"] is True

    # Подписаться повторно - идемпотентно
    res = client.post(f"/api/users/{user_to_follow_id}/follow", headers=auth_headers())
    assert res.status_code == 200
    assert res.json["result"] is True

    # Отписаться
    res = client.delete(f"/api/users/{user_to_follow_id}/follow", headers=auth_headers())
    assert res.status_code == 200
    assert res.json["result"] is True

    # Отписаться повторно - идемпотентно
    res = client.delete(f"/api/users/{user_to_follow_id}/follow", headers=auth_headers())
    assert res.status_code == 200
    assert res.json["result"] is True


def test_get_my_profile(client):
    res = client.get("/api/users/me", headers=auth_headers())
    assert res.status_code == 200
    resp_json = res.get_json()
    assert resp_json["result"] is True
    assert "user" in resp_json
    assert resp_json["user"]["name"] == "TestUser"


def test_get_user_profile(client):
    # Create another user first
    with client.application.app_context():
        other_user = User(name="OtherUser", api_key="other_api_key")
        db.session.add(other_user)
        db.session.commit()
        user_id = other_user.id

    res = client.get(f"/api/users/{user_id}", headers=auth_headers())
    assert res.status_code == 200
    resp_json = res.get_json()
    assert resp_json["result"] is True
    assert resp_json["user"]["name"] == "OtherUser"


def test_get_timeline(client, app):
    with app.app_context():
        user = User.query.filter_by(api_key="test_api_key").first()
        # твит текущего пользователя
        tweet1 = Tweet(content="My tweet", user_id=user.id)
        # твит другого пользователя
        other_user = User(name="OtherUser", api_key="other_api_key")
        db.session.add(other_user)
        db.session.commit()
        tweet2 = Tweet(content="Other tweet", user_id=other_user.id)
        # подписаться на другого пользователя
        user.following.append(other_user)
        db.session.add_all([tweet1, tweet2])
        db.session.commit()

    res = client.get("/api/tweets", headers=auth_headers())
    assert res.status_code == 200
    resp_json = res.get_json()
    assert resp_json["result"] is True
    tweets = resp_json["tweets"]
    contents = [t["content"] for t in tweets]
    assert "My tweet" in contents
    assert "Other tweet" in contents
