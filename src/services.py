from typing import List, Optional, Tuple

from sqlalchemy.exc import SQLAlchemyError

from src.models import Media, Tweet, User, db


def create_tweet(
    user: User, content: str, media_ids: Optional[List[int]] = None
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Создает твит пользователя с опциональными медиа.
    Возвращает: (успех, id твита, сообщение об ошибке)
    """
    try:
        tweet = Tweet(content=content, user_id=user.id)
        db.session.add(tweet)
        db.session.flush()

        if media_ids:
            medias = Media.query.filter(
                Media.id.in_(media_ids),
                Media.user_id == user.id,
            ).all()
            for media in medias:
                media.tweet_id = tweet.id

        db.session.commit()
        return True, tweet.id, None
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, None, str(e)


def upload_media(
    user: User, filename: str, path: str
) -> Tuple[bool, Optional[int], Optional[str]]:
    """
    Сохраняет информацию о загруженном медиа.
    Возвращает: (успех, id медиа, сообщение об ошибке)
    """
    try:
        media = Media(filename=filename, path=path, user_id=user.id)
        db.session.add(media)
        db.session.commit()
        return True, media.id, None
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, None, str(e)


def delete_tweet(user: User, tweet_id: int) -> Tuple[bool, Optional[str]]:
    """
    Удаляет твит, если он принадлежит пользователю.
    Возвращает: (успех, сообщение об ошибке)
    """
    tweet = Tweet.query.get(tweet_id)
    if not tweet:
        return False, "Твит не найден"
    if tweet.user_id != user.id:
        return False, "Удалять можно только свои твиты"
    try:
        db.session.delete(tweet)
        db.session.commit()
        return True, None
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, str(e)


def like_tweet(user: User, tweet_id: int) -> Tuple[bool, Optional[str]]:
    tweet = Tweet.query.get(tweet_id)
    if not tweet:
        return False, "Твит не найден"

    existing_like = tweet.likes.filter(User.id == user.id).first()
    if existing_like:
        return True, None

    try:
        tweet.likes.append(user)
        db.session.commit()
        return True, None
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, str(e)


def unlike_tweet(user: User, tweet_id: int) -> Tuple[bool, Optional[str]]:
    tweet = Tweet.query.get(tweet_id)
    if not tweet:
        return False, "Твит не найден"

    existing_like = tweet.likes.filter(User.id == user.id).first()
    if not existing_like:
        return True, None

    try:
        tweet.likes.remove(user)
        db.session.commit()
        return True, None
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, str(e)


def follow_user(user: User, user_id_to_follow: int) -> Tuple[bool, Optional[str]]:
    if user.id == user_id_to_follow:
        return False, "Нельзя подписаться на себя"

    user_to_follow = User.query.get(user_id_to_follow)
    if not user_to_follow:
        return False, "Пользователь не найден"

    if user_to_follow in user.following:
        return True, None

    try:
        user.following.append(user_to_follow)
        db.session.commit()
        return True, None
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, str(e)


def unfollow_user(user: User, user_id_to_unfollow: int) -> Tuple[bool, Optional[str]]:
    user_to_unfollow = User.query.get(user_id_to_unfollow)
    if not user_to_unfollow:
        return False, "Пользователь не найден"

    if user_to_unfollow not in user.following:
        return True, None

    try:
        user.following.remove(user_to_unfollow)
        db.session.commit()
        return True, None
    except SQLAlchemyError as e:
        db.session.rollback()
        return False, str(e)


def get_timeline(user: User) -> List[dict]:
    followed_ids = [u.id for u in user.following]
    tweets_query = Tweet.query.filter(
        (Tweet.user_id == user.id) | (Tweet.user_id.in_(followed_ids))
    ).order_by(Tweet.created_at.desc())

    tweets = []
    for tweet in tweets_query.all():
        attachments = [media.get_url() for media in tweet.medias]
        likes = [{"user_id": u.id, "name": u.name} for u in tweet.likes]
        tweets.append(
            {
                "id": tweet.id,
                "content": tweet.content,
                "attachments": attachments,
                "author": {"id": tweet.user.id, "name": tweet.user.name},
                "likes": likes,
            }
        )
    return tweets


def get_user_by_id(user_id: int) -> Optional[User]:
    return User.query.get(user_id)
