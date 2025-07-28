from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

followers = db.Table(
    "followers",
    db.Column("follower_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("followed_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
)

likes = db.Table(
    "likes",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
    db.Column("tweet_id", db.Integer, db.ForeignKey("tweet.id"), primary_key=True),
)


class User(db.Model):
    """
    Модель пользователя в базе данных.

    Attributes:
        id (int): Уникальный идентификатор пользователя (первичный ключ).
        name (str): Имя пользователя.
        api_key (str): Уникальный API-ключ пользователя для аутентификации.
        tweets (Query[Tweet]): Динамическая коллекция твитов,
        опубликованных этим пользователем.
        medias (Query[Media]): Динамическая коллекция медиафайлов,
        загруженных этим пользователем.
        following (Query[User]): Динамическая коллекция пользователей,
        на которых подписан данный пользователь.
        liked_tweets (Query[Tweet]): Динамическая коллекция твитов,
        которые понравились пользователю.
    """

    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    api_key = db.Column(db.String(64), unique=True, nullable=False, index=True)

    tweets = db.relationship("Tweet", backref="user", lazy="dynamic")
    medias = db.relationship("Media", backref="user", lazy="dynamic")

    following = db.relationship(
        "User",
        secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref("followers", lazy="dynamic"),
        lazy="dynamic",
    )

    liked_tweets = db.relationship(
        "Tweet", secondary=likes, back_populates="likes", lazy="dynamic"
    )

    def __repr__(self) -> str:
        """
        Возвращает строковое представление объекта User.
        """
        return f"<User {self.name}>"


class Tweet(db.Model):
    """
    Модель твита в базе данных.

    Attributes:
        id (int): Уникальный идентификатор твита (первичный ключ).
        content (str): Содержимое твита (текст).
        created_at (datetime): Дата и время создания твита (UTC).
        user_id (int): Идентификатор пользователя,
        опубликовавшего твит (внешний ключ).
        medias (Query[Media]): Динамическая коллекция медиафайлов,
        прикрепленных к этому твиту.
        likes (Query[User]): Динамическая коллекция пользователей,
        которые поставили лайк этому твиту.
    """

    __tablename__ = "tweet"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(280), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    medias = db.relationship("Media", backref="tweet", lazy="dynamic")

    likes = db.relationship(
        "User", secondary=likes, back_populates="liked_tweets", lazy="dynamic"
    )

    def __repr__(self) -> str:
        """
        Возвращает строковое представление объекта Tweet.
        """
        return f"<Tweet {self.id} by User {self.user_id}>"


class Media(db.Model):
    """
    Модель медиафайла (изображения/видео) в базе данных.

    Attributes:
        id (int): Уникальный идентификатор медиафайла (первичный ключ).
        filename (str): Имя файла медиафайла.
        path (str): Полный путь к файлу медиафайла на сервере.
        uploaded_at (datetime): Дата и время загрузки медиафайла (UTC).
        user_id (int): Идентификатор пользователя,
        загрузившего медиафайл (внешний ключ).
        tweet_id (int, optional): Идентификатор твита,
        к которому прикреплен медиафайл (внешний ключ, может быть None).
    """

    __tablename__ = "media"
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    path = db.Column(db.String(512), nullable=False)
    uploaded_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    tweet_id = db.Column(db.Integer, db.ForeignKey("tweet.id"), nullable=True)

    def __repr__(self) -> str:
        """
        Возвращает строковое представление объекта Media.
        """
        return f"<Media {self.filename} ({self.id})>"

    def get_url(self) -> str:
        """
        Генерирует URL для доступа к медиафайлу через статический сервер.

        Возвращает:
            str: URL медиафайла.
        """
        return f"/static/uploads/{self.filename}"
