import os
import time
import requests

from dotenv import load_dotenv
from urllib3.exceptions import ProtocolError

load_dotenv()


TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

TMDB_TIMEOUT = 30
MAX_RETRIES = 5


def tmdb_get(endpoint, params=None):

    token = os.getenv("TMDB_API_READ_ACCESS_TOKEN")

    if not token:
        raise RuntimeError(
            "TMDB_API_READ_ACCESS_TOKEN is missing from .env"
        )

    url = f"{TMDB_BASE_URL}{endpoint}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "SAM-Movie-Recommender/1.0"
    }

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:

            with requests.Session() as http:

                response = http.get(
                    url,
                    headers=headers,
                    params=params or {},
                    timeout=TMDB_TIMEOUT
                )

                response.raise_for_status()

                return response.json()

        except (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            ProtocolError
        ) as error:

            last_error = error

            print(
                f"TMDB request failed "
                f"(attempt {attempt}/{MAX_RETRIES}): {error}"
            )

            if attempt < MAX_RETRIES:

                delay = min(
                    2 * attempt,
                    10
                )

                time.sleep(delay)

        except requests.exceptions.HTTPError as error:

            status = (
                error.response.status_code
                if error.response is not None
                else None
            )

            if status in (401, 403):

                raise RuntimeError(
                    f"TMDB authentication failed "
                    f"(HTTP {status}). "
                    f"Check TMDB_API_READ_ACCESS_TOKEN."
                ) from error

            if status == 429:

                retry_after = 5

                if error.response is not None:

                    try:

                        retry_after = int(
                            error.response.headers.get(
                                "Retry-After",
                                5
                            )
                        )

                    except (
                        TypeError,
                        ValueError
                    ):

                        pass

                print(
                    f"TMDB rate limit reached. "
                    f"Waiting {retry_after} seconds..."
                )

                time.sleep(retry_after)

                last_error = error

                continue

            raise

    raise last_error


# --------------------------------------------------
# POPULAR MOVIES
# --------------------------------------------------

def get_popular_movies(page=1):

    return tmdb_get(
        "/movie/popular",
        {
            "language": "en-US",
            "page": page
        }
    )


# --------------------------------------------------
# MOVIE DETAILS
# --------------------------------------------------

def get_movie_details(tmdb_movie_id):

    return tmdb_get(
        f"/movie/{tmdb_movie_id}",
        {
            "language": "en-US"
        }
    )


# --------------------------------------------------
# MOVIE CREDITS
# --------------------------------------------------

def get_movie_credits(tmdb_movie_id):

    return tmdb_get(
        f"/movie/{tmdb_movie_id}/credits",
        {
            "language": "en-US"
        }
    )


# --------------------------------------------------
# MOVIE KEYWORDS
# --------------------------------------------------

def get_movie_keywords(tmdb_movie_id):

    return tmdb_get(
        f"/movie/{tmdb_movie_id}/keywords"
    )


# --------------------------------------------------
# SIMILAR MOVIES
# --------------------------------------------------

def get_similar_movies(tmdb_movie_id):

    return tmdb_get(
        f"/movie/{tmdb_movie_id}/similar",
        {
            "language": "en-US",
            "page": 1
        }
    )


# --------------------------------------------------
# POSTER URL
# --------------------------------------------------

def get_poster_url(poster_path):

    if not poster_path:
        return None

    return f"{TMDB_IMAGE_BASE}{poster_path}"