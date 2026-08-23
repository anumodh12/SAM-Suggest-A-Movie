import sys
import time
import json

from pathlib import Path


# --------------------------------------------------
# PROJECT ROOT
# --------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent

sys.path.insert(
    0,
    str(PROJECT_ROOT)
)


# --------------------------------------------------
# APP
# --------------------------------------------------

from app import app

from models.models import db, Movie

from services.tmdb import (
    get_movie_details,
    get_movie_credits,
    get_movie_keywords
)


# --------------------------------------------------
# HELPER
# --------------------------------------------------

def save_json_list(items):

    if not items:
        return None

    return json.dumps(
        items,
        ensure_ascii=False
    )


# --------------------------------------------------
# REPAIR
# --------------------------------------------------

def repair_metadata():

    with app.app_context():

        movies = Movie.query.all()

        total = len(movies)

        repaired = 0

        skipped = 0

        failed = 0


        print()
        print("=" * 60)
        print("SAM METADATA REPAIR")
        print("=" * 60)
        print()

        print(
            f"Movies in database: {total}"
        )

        print()


        for index, movie in enumerate(
            movies,
            start=1
        ):

            # ------------------------------------------
            # Determine whether metadata is missing
            # ------------------------------------------

            missing = (
                not movie.genres
                or not movie.directors
                or not movie.cast
                or not movie.keywords
            )


            if not missing:

                skipped += 1

                continue


            print(
                f"[{index}/{total}] "
                f"Repairing: {movie.title}"
            )


            try:

                # --------------------------------------
                # DETAILS
                # --------------------------------------

                details = get_movie_details(
                    movie.tmdb_id
                )


                genres = [
                    genre.get("name")
                    for genre in details.get(
                        "genres",
                        []
                    )
                    if genre.get("name")
                ]


                # --------------------------------------
                # CREDITS
                # --------------------------------------

                credits = get_movie_credits(
                    movie.tmdb_id
                )


                cast = [
                    person.get("name")
                    for person in credits.get(
                        "cast",
                        []
                    )[:15]
                    if person.get("name")
                ]


                directors = [
                    person.get("name")
                    for person in credits.get(
                        "crew",
                        []
                    )
                    if person.get("job") == "Director"
                ]


                # --------------------------------------
                # KEYWORDS
                # --------------------------------------

                keyword_data = get_movie_keywords(
                    movie.tmdb_id
                )


                keywords = [
                    keyword.get("name")
                    for keyword in keyword_data.get(
                        "keywords",
                        []
                    )
                    if keyword.get("name")
                ]


                # --------------------------------------
                # ONLY UPDATE WHEN DATA EXISTS
                # --------------------------------------

                if genres:
                    movie.genres = save_json_list(
                        genres
                    )


                if cast:
                    movie.cast = save_json_list(
                        cast
                    )


                if directors:
                    movie.directors = save_json_list(
                        directors
                    )


                if keywords:
                    movie.keywords = save_json_list(
                        keywords
                    )


                db.session.commit()


                repaired += 1


                print(
                    "    OK"
                )


                print(
                    f"    Genres: {len(genres)}"
                )

                print(
                    f"    Directors: {len(directors)}"
                )

                print(
                    f"    Cast: {len(cast)}"
                )

                print(
                    f"    Keywords: {len(keywords)}"
                )


                # --------------------------------------
                # DELAY
                # --------------------------------------

                time.sleep(1)


            except Exception as error:

                db.session.rollback()

                failed += 1

                print(
                    f"    FAILED: {error}"
                )

                print(
                    "    Continuing..."
                )

                time.sleep(2)


        print()
        print("=" * 60)
        print("REPAIR FINISHED")
        print("=" * 60)

        print(
            f"Repaired: {repaired}"
        )

        print(
            f"Already complete: {skipped}"
        )

        print(
            f"Failed: {failed}"
        )

        print()


# --------------------------------------------------
# RUN
# --------------------------------------------------

if __name__ == "__main__":

    repair_metadata()