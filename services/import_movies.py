import sys
import json
import time

from pathlib import Path


# --------------------------------------------------
# PROJECT ROOT
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(
    0,
    str(PROJECT_ROOT)
)


# --------------------------------------------------
# APP IMPORTS
# --------------------------------------------------

from app import app

from models.models import db, Movie

from services.tmdb import (
    get_popular_movies,
    get_movie_details,
    get_movie_credits,
    get_movie_keywords
)


# --------------------------------------------------
# HELPERS
# --------------------------------------------------

def save_json_list(items):

    if not items:
        return None

    return json.dumps(
        items,
        ensure_ascii=False
    )


# --------------------------------------------------
# IMPORT MOVIES
# --------------------------------------------------

def import_movies(pages=5):

    imported = 0

    updated = 0


    with app.app_context():

        for page in range(1, pages + 1):

            print()
            print(
                f"Fetching TMDB popular page {page}..."
            )


            data = get_popular_movies(page)

            movies = data.get(
                "results",
                []
            )


            for index, movie_data in enumerate(
                movies,
                start=1
            ):

                tmdb_id = movie_data.get("id")


                if not tmdb_id:
                    continue


                print(
                    f"  [{index}/{len(movies)}] "
                    f"{movie_data.get('title')}"
                )


                # ----------------------------------
                # Check existing movie
                # ----------------------------------

                movie = Movie.query.filter_by(
                    tmdb_id=tmdb_id
                ).first()


                # ----------------------------------
                # Basic movie information
                # ----------------------------------

                title = movie_data.get(
                    "title"
                )

                overview = movie_data.get(
                    "overview"
                )

                poster_path = movie_data.get(
                    "poster_path"
                )

                backdrop_path = movie_data.get(
                    "backdrop_path"
                )

                release_date = movie_data.get(
                    "release_date"
                )

                rating = movie_data.get(
                    "vote_average"
                )

                language = movie_data.get(
                    "original_language"
                )


                try:

                    # ----------------------------------
                    # Detailed movie information
                    # ----------------------------------

                    details = get_movie_details(
                        tmdb_id
                    )


                    # ----------------------------------
                    # Genres
                    # ----------------------------------

                    genres = [
                        genre.get("name")
                        for genre in details.get(
                            "genres",
                            []
                        )
                        if genre.get("name")
                    ]


                    # ----------------------------------
                    # Credits
                    # ----------------------------------

                    credits = get_movie_credits(
                        tmdb_id
                    )


                    # ----------------------------------
                    # Cast
                    # ----------------------------------

                    cast = [
                        person.get("name")
                        for person in credits.get(
                            "cast",
                            []
                        )[:15]
                        if person.get("name")
                    ]


                    # ----------------------------------
                    # Directors
                    # ----------------------------------

                    directors = [
                        person.get("name")
                        for person in credits.get(
                            "crew",
                            []
                        )
                        if person.get("job") == "Director"
                    ]


                    # ----------------------------------
                    # Keywords
                    # ----------------------------------

                    keyword_data = get_movie_keywords(
                        tmdb_id
                    )


                    keywords = [
                        keyword.get("name")
                        for keyword in keyword_data.get(
                            "keywords",
                            []
                        )
                        if keyword.get("name")
                    ]


                    # ----------------------------------
                    # Create movie
                    # ----------------------------------

                    if not movie:

                        movie = Movie(
                            tmdb_id=tmdb_id,
                            title=title,
                            overview=overview,
                            poster_path=poster_path,
                            backdrop_path=backdrop_path,
                            release_date=release_date,
                            rating=rating,
                            language=language,

                            genres=save_json_list(
                                genres
                            ),

                            keywords=save_json_list(
                                keywords
                            ),

                            cast=save_json_list(
                                cast
                            ),

                            directors=save_json_list(
                                directors
                            )
                        )


                        db.session.add(movie)

                        imported += 1


                    # ----------------------------------
                    # Update existing movie
                    # ----------------------------------

                    else:

                        movie.title = title

                        movie.overview = overview

                        movie.poster_path = poster_path

                        movie.backdrop_path = backdrop_path

                        movie.release_date = release_date

                        movie.rating = rating

                        movie.language = language

                        movie.genres = save_json_list(
                            genres
                        )

                        movie.keywords = save_json_list(
                            keywords
                        )

                        movie.cast = save_json_list(
                            cast
                        )

                        movie.directors = save_json_list(
                            directors
                        )


                        updated += 1


                    # ----------------------------------
                    # Commit this movie
                    # ----------------------------------

                    db.session.commit()


                    # Small delay so we don't hammer TMDB
                    time.sleep(0.15)


                except Exception as error:

                    db.session.rollback()


                    print(
                        f"    ERROR: {error}"
                    )

                    continue


            print(
                f"Finished page {page}"
            )


    print()
    print(
        f"Imported new movies: {imported}"
    )

    print(
        f"Updated existing movies: {updated}"
    )


# --------------------------------------------------
# RUN
# --------------------------------------------------

if __name__ == "__main__":

    import_movies(
        pages=25
    )


