from datetime import datetime

from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class Movie(db.Model):
    __tablename__ = "movies"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    tmdb_id = db.Column(
        db.Integer,
        unique=True,
        nullable=False
    )

    title = db.Column(
        db.String(255),
        nullable=False
    )

    overview = db.Column(
        db.Text
    )

    poster_path = db.Column(
        db.String(255)
    )

    backdrop_path = db.Column(
        db.String(255)
    )

    release_date = db.Column(
        db.String(20)
    )

    rating = db.Column(
        db.Float
    )

    language = db.Column(
        db.String(20)
    )

    # -----------------------------------------
    # MOVIE TASTE DATA
    # -----------------------------------------

    # Stored as JSON strings.
    #
    # Example:
    # ["Science Fiction", "Thriller", "Drama"]

    genres = db.Column(
        db.Text
    )

    # Example:
    # ["time travel", "space", "artificial intelligence"]

    keywords = db.Column(
        db.Text
    )

    # Example:
    # ["Leonardo DiCaprio", "Joseph Gordon-Levitt"]

    cast = db.Column(
        db.Text
    )

    # Example:
    # ["Christopher Nolan"]

    directors = db.Column(
        db.Text
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )


class MoviePreference(db.Model):
    __tablename__ = "movie_preferences"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    movie_id = db.Column(
        db.Integer,
        db.ForeignKey("movies.id"),
        nullable=False
    )

    preference = db.Column(
        db.String(20),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    movie = db.relationship(
        "Movie",
        backref=db.backref(
            "preferences",
            lazy=True
        )
    )


class Swipe(db.Model):

    __tablename__ = "swipes"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    movie_id = db.Column(
        db.Integer,
        db.ForeignKey("movies.id"),
        nullable=False
    )

    action = db.Column(
        db.String(20),
        nullable=False
    )

    session_id = db.Column(
        db.String(100),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    movie = db.relationship(
        "Movie",
        backref=db.backref(
            "swipes",
            lazy=True
        )
    )