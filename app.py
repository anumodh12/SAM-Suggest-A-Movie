import json
import os
import uuid
from collections import Counter, defaultdict

from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from models.models import db, Movie, Swipe
from services.tmdb import get_popular_movies


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# FLASK APPLICATION
# ============================================================

app = Flask(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "development-secret-change-this"
)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///sam.db"

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False


# ============================================================
# DATABASE
# ============================================================

db.init_app(app)


with app.app_context():
    db.create_all()


# ============================================================
# APPLICATION CONSTANTS
# ============================================================

MAX_DISCOVERY_MOVIES = 20

MAX_RECOMMENDATIONS = 60

# Keep the browser-session list reasonably small.
# This prevents the Flask session cookie from becoming too large
# after many repeated tests.
MAX_HISTORY_MOVIES = 500


VALID_ACTIONS = {
    "like",
    "very-like",
    "dislike",
    "not-seen",
}


ACTION_WEIGHTS = {
    "very-like": 4.0,
    "like": 2.0,
    "not-seen": 0.0,
    "dislike": -6.0,
}


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return render_template("index.html")


# ============================================================
# SESSION HELPERS
# ============================================================

def create_new_discovery_session():
    """
    Create a completely new discovery-test session.

    Before replacing the current test ID, remember the movies
    used by the current test so future retakes can avoid them.
    """

    remember_current_test_movies()

    session["sam_session_id"] = str(uuid.uuid4())

    session["discovery_active"] = True

    session["discovery_complete"] = False

    session["test_complete"] = False

    session.modified = True

    return session["sam_session_id"]


def remember_current_test_movies():
    """
    Add movies from the current discovery test to the browser
    session's used-movie history.

    This lets Retake Test produce a genuinely different set.
    """

    current_session_id = session.get("sam_session_id")

    if not current_session_id:
        return

    try:
        swipes = Swipe.query.filter_by(
            session_id=current_session_id
        ).all()

        used_ids = set(
            session.get(
                "sam_used_discovery_movie_ids",
                []
            )
        )

        for swipe in swipes:
            if swipe.movie_id is not None:
                used_ids.add(int(swipe.movie_id))

        # Keep only the most recent IDs.
        used_ids = list(used_ids)[-MAX_HISTORY_MOVIES:]

        session["sam_used_discovery_movie_ids"] = used_ids

        session.modified = True

    except Exception:
        # Do not allow history bookkeeping to break a new test.
        pass


def get_current_session_id():
    """
    Return the current SAM discovery session ID.
    """

    return session.get("sam_session_id")


def get_current_swipes():
    """
    Return all swipes belonging to the current discovery test.
    """

    session_id = get_current_session_id()

    if not session_id:
        return []

    return Swipe.query.filter_by(
        session_id=session_id
    ).all()


def get_current_swiped_movie_ids():
    """
    Return IDs of movies swiped in the current test.
    """

    return {
        swipe.movie_id
        for swipe in get_current_swipes()
        if swipe.movie_id is not None
    }


def get_all_browser_used_movie_ids():
    """
    Return all movies that have been used in previous discovery
    tests in this browser session.

    Also includes movies from the current test.
    """

    used_ids = set()

    stored_ids = session.get(
        "sam_used_discovery_movie_ids",
        []
    )

    for movie_id in stored_ids:
        try:
            used_ids.add(int(movie_id))
        except (TypeError, ValueError):
            continue

    current_swiped_ids = get_current_swiped_movie_ids()

    used_ids.update(current_swiped_ids)

    return used_ids


# ============================================================
# START NEW DISCOVERY TEST
# ============================================================

@app.route("/start-test")
def start_test():
    """
    Start a completely new discovery test.
    """

    create_new_discovery_session()

    return redirect(
        url_for("discover")
    )


# ============================================================
# RESET / RETAKE TEST
# ============================================================

@app.route("/reset-test")
def reset_test():
    """
    Retake the discovery test using a new session ID and,
    importantly, avoid movies already used by previous tests.
    """

    create_new_discovery_session()

    return redirect(
        url_for("discover")
    )


# ============================================================
# OPTIONAL JSON RETAKE ENDPOINT
# ============================================================

@app.route("/api/retake-test", methods=["POST"])
def api_retake_test():
    """
    JSON version of Retake Test.

    Useful if recommendations.html later wants to trigger
    the retake without navigating directly through an <a> tag.
    """

    create_new_discovery_session()

    return jsonify({
        "success": True,
        "redirect": url_for("discover"),
        "session_id": session["sam_session_id"],
    })


# ============================================================
# METADATA HELPERS
# ============================================================

def parse_metadata(value):
    """
    Convert stored metadata into a normalized list.

    Supports:

        ["Action", "Drama"]

    JSON strings:

        '["Action", "Drama"]'

    Comma-separated strings:

        "Action, Drama"

    Dictionary values are also supported.
    """

    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):

        return [
            str(item).strip().lower()
            for item in value
            if str(item).strip()
        ]

    if isinstance(value, dict):

        return [
            str(item).strip().lower()
            for item in value.values()
            if str(item).strip()
        ]

    value = str(value).strip()

    if not value:
        return []

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    try:

        parsed = json.loads(value)

        if isinstance(parsed, list):

            return [
                str(item).strip().lower()
                for item in parsed
                if str(item).strip()
            ]

        if isinstance(parsed, dict):

            return [
                str(item).strip().lower()
                for item in parsed.values()
                if str(item).strip()
            ]

    except (
        json.JSONDecodeError,
        TypeError,
        ValueError
    ):
        pass

    # --------------------------------------------------------
    # FALLBACK: COMMA SEPARATED
    # --------------------------------------------------------

    return [
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    ]


def first_metadata_value(value):
    """
    Return the first metadata item.
    Used by discovery diversification.
    """

    values = parse_metadata(value)

    if not values:
        return None

    return values[0]


def get_movie_year(movie):
    """
    Safely extract release year.
    """

    if not movie.release_date:
        return None

    value = str(movie.release_date).strip()

    if len(value) >= 4:
        return value[:4]

    return None


def safe_rating(movie):
    """
    Safely return a numeric rating.
    """

    if movie.rating is None:
        return 0.0

    try:
        return float(movie.rating)
    except (
        TypeError,
        ValueError
    ):
        return 0.0


# ============================================================
# MOVIE SERIALIZATION
# ============================================================

def movie_to_dict(movie, include_score=False, score=None):
    """
    Convert Movie SQLAlchemy object into JSON-safe data.
    """

    data = {
        "id": movie.id,
        "tmdb_id": movie.tmdb_id,
        "title": movie.title,
        "overview": movie.overview,
        "poster_path": movie.poster_path,
        "backdrop_path": movie.backdrop_path,
        "release_date": movie.release_date,
        "rating": movie.rating,
        "language": movie.language,
        "genres": movie.genres,
        "keywords": movie.keywords,
        "cast": movie.cast,
        "directors": movie.directors,
    }

    if include_score:
        data["score"] = round(
            float(score or 0),
            2
        )

    return data


# ============================================================
# SAVE SWIPE
# ============================================================

@app.route("/api/swipe", methods=["POST"])
def save_swipe():

    data = request.get_json(silent=True) or {}

    movie_id = data.get("movie_id")

    action = data.get("action")

    # --------------------------------------------------------
    # VALIDATE REQUEST
    # --------------------------------------------------------

    if not movie_id or action not in VALID_ACTIONS:

        return jsonify({
            "success": False,
            "error": "Invalid movie or action",
        }), 400

    try:
        movie_id = int(movie_id)
    except (
        TypeError,
        ValueError
    ):

        return jsonify({
            "success": False,
            "error": "Invalid movie ID",
        }), 400

    # --------------------------------------------------------
    # CREATE SESSION IF NECESSARY
    # --------------------------------------------------------

    if "sam_session_id" not in session:

        session["sam_session_id"] = str(uuid.uuid4())

        session["discovery_active"] = True

        session["discovery_complete"] = False

        session["test_complete"] = False

        session.modified = True

    session_id = session["sam_session_id"]

    # --------------------------------------------------------
    # CHECK CURRENT COUNT
    # --------------------------------------------------------

    swipe_count = Swipe.query.filter_by(
        session_id=session_id
    ).count()

    # --------------------------------------------------------
    # DON'T ACCEPT MORE THAN 20
    # --------------------------------------------------------

    if swipe_count >= MAX_DISCOVERY_MOVIES:

        session["test_complete"] = True

        session["discovery_complete"] = True

        session.modified = True

        return jsonify({
            "success": False,
            "limit_reached": True,
            "test_complete": True,
            "swipe_count": swipe_count,
            "remaining": 0,
            "message": (
                "SAM has already learned enough "
                "about your taste."
            ),
        }), 403

    # --------------------------------------------------------
    # FIND MOVIE
    # --------------------------------------------------------

    movie = db.session.get(
        Movie,
        movie_id
    )

    if not movie:

        return jsonify({
            "success": False,
            "error": "Movie not found",
        }), 404

    # --------------------------------------------------------
    # PREVENT DUPLICATE SWIPE
    # --------------------------------------------------------

    already_swiped = Swipe.query.filter_by(
        session_id=session_id,
        movie_id=movie_id
    ).first()

    if already_swiped:

        return jsonify({
            "success": False,
            "error": "Movie already rated",
        }), 409

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    swipe = Swipe(
        movie_id=movie_id,
        action=action,
        session_id=session_id,
    )

    db.session.add(swipe)

    try:

        db.session.commit()

    except Exception as error:

        db.session.rollback()

        return jsonify({
            "success": False,
            "error": str(error),
        }), 500

    # --------------------------------------------------------
    # NEW COUNT
    # --------------------------------------------------------

    new_count = swipe_count + 1

    test_complete = (
        new_count >= MAX_DISCOVERY_MOVIES
    )

    if test_complete:

        session["test_complete"] = True

        session["discovery_complete"] = True

        session["discovery_active"] = True

        # Remember these movies immediately.
        remember_current_test_movies()

        session.modified = True

    # --------------------------------------------------------
    # ALL-DISLIKE STATUS
    # --------------------------------------------------------

    all_disliked = False

    if test_complete:

        current_swipes = get_current_swipes()

        all_disliked = (
            len(current_swipes) == MAX_DISCOVERY_MOVIES
            and all(
                item.action == "dislike"
                for item in current_swipes
            )
        )

    # --------------------------------------------------------
    # RESPONSE
    # --------------------------------------------------------

    return jsonify({

        "success": True,

        "movie_id": movie_id,

        "action": action,

        "swipe_count": new_count,

        "remaining": max(
            0,
            MAX_DISCOVERY_MOVIES - new_count
        ),

        "test_complete": test_complete,

        "all_disliked": all_disliked,

        "recommendations_url": url_for(
            "recommendations"
        ),

    }), 200


# ============================================================
# RECOMMENDATIONS PAGE
# ============================================================

@app.route("/recommendations-page")
def recommendations_page():

    return render_template(
        "recommendations.html"
    )


# ============================================================
# BUILD TASTE PROFILE
# ============================================================

def build_taste_profile(swipes):
    """
    Build the user's weighted taste profile.

    very-like = +4
    like      = +2
    not-seen  =  0
    dislike   = -6
    """

    genre_scores = defaultdict(float)

    keyword_scores = defaultdict(float)

    director_scores = defaultdict(float)

    cast_scores = defaultdict(float)

    language_scores = defaultdict(float)

    genre_counts = defaultdict(int)

    keyword_counts = defaultdict(int)

    director_counts = defaultdict(int)

    cast_counts = defaultdict(int)

    language_counts = defaultdict(int)

    movie_preferences = {}

    for swipe in swipes:

        movie = swipe.movie

        if not movie:

            movie = db.session.get(
                Movie,
                swipe.movie_id
            )

        if not movie:
            continue

        weight = ACTION_WEIGHTS.get(
            swipe.action,
            0.0
        )

        movie_preferences[movie.id] = weight

        if weight == 0:
            continue

        # ----------------------------------------------------
        # GENRES
        # ----------------------------------------------------

        for genre in parse_metadata(
            movie.genres
        ):

            genre_scores[genre] += weight

            genre_counts[genre] += 1

        # ----------------------------------------------------
        # KEYWORDS
        # ----------------------------------------------------

        for keyword in parse_metadata(
            movie.keywords
        ):

            keyword_scores[keyword] += weight

            keyword_counts[keyword] += 1

        # ----------------------------------------------------
        # DIRECTORS
        # ----------------------------------------------------

        for director in parse_metadata(
            movie.directors
        ):

            director_scores[director] += weight

            director_counts[director] += 1

        # ----------------------------------------------------
        # CAST
        # ----------------------------------------------------

        for actor in parse_metadata(
            movie.cast
        ):

            cast_scores[actor] += weight

            cast_counts[actor] += 1

        # ----------------------------------------------------
        # LANGUAGE
        # ----------------------------------------------------

        if movie.language:

            language = str(
                movie.language
            ).strip().lower()

            if language:

                language_scores[language] += weight

                language_counts[language] += 1

    # ========================================================
    # NORMALIZE
    # ========================================================

    for key in list(genre_scores):

        if genre_counts[key]:

            genre_scores[key] /= (
                genre_counts[key]
            )

    for key in list(keyword_scores):

        if keyword_counts[key]:

            keyword_scores[key] /= (
                keyword_counts[key]
            )

    for key in list(director_scores):

        if director_counts[key]:

            director_scores[key] /= (
                director_counts[key]
            )

    for key in list(cast_scores):

        if cast_counts[key]:

            cast_scores[key] /= (
                cast_counts[key]
            )

    for key in list(language_scores):

        if language_counts[key]:

            language_scores[key] /= (
                language_counts[key]
            )

    return {
        "genres": genre_scores,
        "keywords": keyword_scores,
        "directors": director_scores,
        "cast": cast_scores,
        "languages": language_scores,
        "movie_preferences": movie_preferences,
    }


# ============================================================
# ALL-DISLIKE DETECTION
# ============================================================

def is_all_dislike_test(swipes):
    """
    True when the current completed test contains exactly
    20 swipes and every swipe is dislike.
    """

    if len(swipes) != MAX_DISCOVERY_MOVIES:
        return False

    return all(
        swipe.action == "dislike"
        for swipe in swipes
    )


# ============================================================
# RECOMMENDATION SCORING
# ============================================================

def score_candidate_movie(
    movie,
    taste_profile,
):
    """
    Score a movie against the learned taste profile.

    Personal taste dominates rating.
    """

    genre_scores = taste_profile["genres"]

    keyword_scores = taste_profile["keywords"]

    director_scores = taste_profile["directors"]

    cast_scores = taste_profile["cast"]

    language_scores = taste_profile["languages"]

    score = 0.0

    positive_matches = 0

    negative_matches = 0

    # ========================================================
    # GENRES
    # ========================================================

    for genre in parse_metadata(
        movie.genres
    ):

        signal = genre_scores.get(
            genre,
            0.0
        )

        if signal > 0:

            score += signal * 4.0

            positive_matches += 1

        elif signal < 0:

            score += signal * 6.0

            negative_matches += 1

    # ========================================================
    # KEYWORDS
    # ========================================================

    for keyword in parse_metadata(
        movie.keywords
    ):

        signal = keyword_scores.get(
            keyword,
            0.0
        )

        if signal > 0:

            score += signal * 1.5

            positive_matches += 1

        elif signal < 0:

            score += signal * 3.0

            negative_matches += 1

    # ========================================================
    # DIRECTORS
    # ========================================================

    for director in parse_metadata(
        movie.directors
    ):

        signal = director_scores.get(
            director,
            0.0
        )

        if signal > 0:

            score += signal * 5.0

            positive_matches += 1

        elif signal < 0:

            score += signal * 7.0

            negative_matches += 1

    # ========================================================
    # CAST
    # ========================================================

    for actor in parse_metadata(
        movie.cast
    ):

        signal = cast_scores.get(
            actor,
            0.0
        )

        if signal > 0:

            score += signal * 1.5

            positive_matches += 1

        elif signal < 0:

            score += signal * 3.0

            negative_matches += 1

    # ========================================================
    # LANGUAGE
    # ========================================================

    if movie.language:

        language = str(
            movie.language
        ).strip().lower()

        signal = language_scores.get(
            language,
            0.0
        )

        if signal > 0:

            score += signal * 1.5

            positive_matches += 1

        elif signal < 0:

            score += signal * 3.0

            negative_matches += 1

    # ========================================================
    # POSITIVE MATCH BONUS
    # ========================================================

    if positive_matches >= 5:

        score += 8.0

    elif positive_matches >= 4:

        score += 6.0

    elif positive_matches >= 3:

        score += 4.0

    elif positive_matches >= 2:

        score += 2.0

    # ========================================================
    # NEGATIVE PENALTY
    # ========================================================

    if negative_matches >= 5:

        score -= 16.0

    elif negative_matches >= 4:

        score -= 12.0

    elif negative_matches >= 3:

        score -= 8.0

    elif negative_matches >= 2:

        score -= 5.0

    elif negative_matches >= 1:

        score -= 2.0

    # ========================================================
    # QUALITY BONUS
    # ========================================================

    rating = safe_rating(movie)

    if rating > 0:

        # Keep TMDB quality influence small.
        score += min(
            rating,
            10.0
        ) * 0.15

    return score


# ============================================================
# RECOMMENDATIONS API
# ============================================================

# --------------------------------------------------
# RECOMMENDATIONS DATA
# --------------------------------------------------

@app.route("/recommendations")
def recommendations():

    # --------------------------------------------------
    # GET CURRENT SESSION
    # --------------------------------------------------

    if "sam_session_id" not in session:

        return jsonify({

            "liked_count": 0,

            "very_liked_count": 0,

            "disliked_count": 0,

            "not_seen_count": 0,

            "recommendations": [],

            "retake_required": True,

            "no_positive_signals": True,

            "all_disliked": False,

            "all_not_seen": False

        })


    session_id = session["sam_session_id"]


    # --------------------------------------------------
    # GET SWIPES FOR CURRENT TEST ONLY
    # --------------------------------------------------

    swipes = Swipe.query.filter_by(
        session_id=session_id
    ).all()


    if not swipes:

        return jsonify({

            "liked_count": 0,

            "very_liked_count": 0,

            "disliked_count": 0,

            "not_seen_count": 0,

            "recommendations": [],

            "retake_required": False,

            "no_positive_signals": True,

            "all_disliked": False,

            "all_not_seen": False

        })


    # --------------------------------------------------
    # COUNT ACTIONS
    # --------------------------------------------------

    liked_swipes = [
        swipe
        for swipe in swipes
        if swipe.action == "like"
    ]


    very_liked_swipes = [
        swipe
        for swipe in swipes
        if swipe.action == "very-like"
    ]


    disliked_swipes = [
        swipe
        for swipe in swipes
        if swipe.action == "dislike"
    ]


    not_seen_swipes = [
        swipe
        for swipe in swipes
        if swipe.action == "not-seen"
    ]


    # --------------------------------------------------
    # POSITIVE SIGNALS
    #
    # ONLY LIKE / VERY-LIKE COUNT AS POSITIVE.
    #
    # NOT-SEEN = 0
    # DISLIKE  = negative
    # --------------------------------------------------

    positive_swipes = [
        swipe
        for swipe in swipes
        if swipe.action in (
            "like",
            "very-like"
        )
    ]


    # --------------------------------------------------
    # MOVIES ALREADY RATED IN THIS TEST
    #
    # VERY IMPORTANT:
    #
    # ALL four actions are excluded:
    #
    # like
    # very-like
    # dislike
    # not-seen
    #
    # Therefore SAM can NEVER recommend a movie
    # that the user already saw during this test.
    # --------------------------------------------------

    swiped_movie_ids = {
        swipe.movie_id
        for swipe in swipes
        if swipe.movie_id is not None
    }


    # --------------------------------------------------
    # SPECIAL CASE:
    #
    # NO POSITIVE SIGNALS
    #
    # Examples:
    #
    # 20 x dislike
    # 20 x not-seen
    # 10 x dislike + 10 x not-seen
    #
    # SAM does NOT have evidence of what the user likes.
    #
    # DO NOT RECOMMEND A RANDOM MOVIE.
    # ASK USER TO RETAKE THE TEST.
    # --------------------------------------------------

    if not positive_swipes:

        all_disliked = (
            len(disliked_swipes) == len(swipes)
        )


        all_not_seen = (
            len(not_seen_swipes) == len(swipes)
        )


        return jsonify({

            "liked_count":
                len(liked_swipes),

            "very_liked_count":
                len(very_liked_swipes),

            "disliked_count":
                len(disliked_swipes),

            "not_seen_count":
                len(not_seen_swipes),

            "recommendations": [],

            "retake_required": True,

            "no_matches": True,

            "no_positive_signals": True,

            "all_disliked": all_disliked,

            "all_not_seen": all_not_seen

        })


    # --------------------------------------------------
    # TASTE PROFILE
    # --------------------------------------------------

    genre_scores = defaultdict(float)

    keyword_scores = defaultdict(float)

    director_scores = defaultdict(float)

    cast_scores = defaultdict(float)

    language_scores = defaultdict(float)


    genre_counts = defaultdict(int)

    keyword_counts = defaultdict(int)

    director_counts = defaultdict(int)

    cast_counts = defaultdict(int)

    language_counts = defaultdict(int)


    # --------------------------------------------------
    # ACTION WEIGHTS
    # --------------------------------------------------

    ACTION_WEIGHTS = {

        "very-like": 4.0,

        "like": 2.0,

        "dislike": -6.0,

        "not-seen": 0.0

    }


    # --------------------------------------------------
    # PARSE MOVIE METADATA
    # --------------------------------------------------

    def parse_values(value):

        if not value:

            return []


        # Already a Python list

        if isinstance(value, list):

            return [

                str(item).strip().lower()

                for item in value

                if str(item).strip()

            ]


        # Database normally stores JSON text

        if not isinstance(value, str):

            return []


        value = value.strip()


        if not value:

            return []


        # --------------------------------------------------
        # TRY JSON
        # --------------------------------------------------

        try:

            parsed = json.loads(value)


            if isinstance(parsed, list):

                return [

                    str(item).strip().lower()

                    for item in parsed

                    if str(item).strip()

                ]


            if isinstance(parsed, dict):

                return [

                    str(item).strip().lower()

                    for item in parsed.values()

                    if str(item).strip()

                ]


        except (
            json.JSONDecodeError,
            TypeError
        ):

            pass


        # --------------------------------------------------
        # FALLBACK
        # --------------------------------------------------

        return [

            item.strip().lower()

            for item in value.split(",")

            if item.strip()

        ]


    # --------------------------------------------------
    # LEARN FROM SWIPES
    # --------------------------------------------------

    for swipe in swipes:

        movie = swipe.movie

        if not movie:

            movie = db.session.get(
                Movie,
                swipe.movie_id
            )


        if not movie:

            continue


        weight = ACTION_WEIGHTS.get(
            swipe.action,
            0.0
        )


        # NOT-SEEN DOES NOT TEACH SAM
        if weight == 0:

            continue


        # --------------------------------------------------
        # GENRES
        # --------------------------------------------------

        for genre in parse_values(
            movie.genres
        ):

            genre_scores[genre] += weight

            genre_counts[genre] += 1


        # --------------------------------------------------
        # KEYWORDS
        # --------------------------------------------------

        for keyword in parse_values(
            movie.keywords
        ):

            keyword_scores[keyword] += weight

            keyword_counts[keyword] += 1


        # --------------------------------------------------
        # DIRECTORS
        # --------------------------------------------------

        for director in parse_values(
            movie.directors
        ):

            director_scores[director] += weight

            director_counts[director] += 1


        # --------------------------------------------------
        # CAST
        # --------------------------------------------------

        for actor in parse_values(
            movie.cast
        ):

            cast_scores[actor] += weight

            cast_counts[actor] += 1


        # --------------------------------------------------
        # LANGUAGE
        # --------------------------------------------------

        if movie.language:

            language = (
                movie.language
                .strip()
                .lower()
            )

            if language:

                language_scores[language] += weight

                language_counts[language] += 1


    # --------------------------------------------------
    # NORMALIZE GENRES
    # --------------------------------------------------

    for key in list(genre_scores):

        if genre_counts[key]:

            genre_scores[key] /= (
                genre_counts[key]
            )


    # --------------------------------------------------
    # NORMALIZE KEYWORDS
    # --------------------------------------------------

    for key in list(keyword_scores):

        if keyword_counts[key]:

            keyword_scores[key] /= (
                keyword_counts[key]
            )


    # --------------------------------------------------
    # NORMALIZE DIRECTORS
    # --------------------------------------------------

    for key in list(director_scores):

        if director_counts[key]:

            director_scores[key] /= (
                director_counts[key]
            )


    # --------------------------------------------------
    # NORMALIZE CAST
    # --------------------------------------------------

    for key in list(cast_scores):

        if cast_counts[key]:

            cast_scores[key] /= (
                cast_counts[key]
            )


    # --------------------------------------------------
    # NORMALIZE LANGUAGE
    # --------------------------------------------------

    for key in list(language_scores):

        if language_counts[key]:

            language_scores[key] /= (
                language_counts[key]
            )


    # --------------------------------------------------
    # GET CANDIDATE MOVIES
    #
    # NEVER INCLUDE ANY MOVIE ALREADY RATED
    # IN THIS TEST.
    # --------------------------------------------------

    if swiped_movie_ids:

        candidates = Movie.query.filter(
            ~Movie.id.in_(swiped_movie_ids)
        ).all()

    else:

        candidates = Movie.query.all()


    # --------------------------------------------------
    # SAFETY CHECK
    # --------------------------------------------------

    if not candidates:

        return jsonify({

            "liked_count":
                len(liked_swipes),

            "very_liked_count":
                len(very_liked_swipes),

            "disliked_count":
                len(disliked_swipes),

            "not_seen_count":
                len(not_seen_swipes),

            "recommendations": [],

            "retake_required": True,

            "no_matches": True,

            "no_positive_signals": False,

            "all_disliked": False,

            "all_not_seen": False

        })


    # --------------------------------------------------
    # SCORE MOVIES
    # --------------------------------------------------

    scored_movies = []


    for movie in candidates:

        score = 0.0

        positive_matches = 0

        negative_matches = 0


        # --------------------------------------------------
        # GENRES
        # --------------------------------------------------

        for genre in parse_values(
            movie.genres
        ):

            signal = genre_scores.get(
                genre,
                0.0
            )


            if signal > 0:

                score += signal * 4.0

                positive_matches += 1


            elif signal < 0:

                score += signal * 6.0

                negative_matches += 1


        # --------------------------------------------------
        # KEYWORDS
        # --------------------------------------------------

        for keyword in parse_values(
            movie.keywords
        ):

            signal = keyword_scores.get(
                keyword,
                0.0
            )


            if signal > 0:

                score += signal * 1.5

                positive_matches += 1


            elif signal < 0:

                score += signal * 3.0

                negative_matches += 1


        # --------------------------------------------------
        # DIRECTORS
        # --------------------------------------------------

        for director in parse_values(
            movie.directors
        ):

            signal = director_scores.get(
                director,
                0.0
            )


            if signal > 0:

                score += signal * 5.0

                positive_matches += 1


            elif signal < 0:

                score += signal * 7.0

                negative_matches += 1


        # --------------------------------------------------
        # CAST
        # --------------------------------------------------

        for actor in parse_values(
            movie.cast
        ):

            signal = cast_scores.get(
                actor,
                0.0
            )


            if signal > 0:

                score += signal * 1.5

                positive_matches += 1


            elif signal < 0:

                score += signal * 3.0

                negative_matches += 1


        # --------------------------------------------------
        # LANGUAGE
        # --------------------------------------------------

        if movie.language:

            language = (
                movie.language
                .strip()
                .lower()
            )


            signal = language_scores.get(
                language,
                0.0
            )


            if signal > 0:

                score += signal * 1.5

                positive_matches += 1


            elif signal < 0:

                score += signal * 3.0

                negative_matches += 1


        # --------------------------------------------------
        # POSITIVE MATCH BONUS
        # --------------------------------------------------

        if positive_matches >= 4:

            score += 6.0

        elif positive_matches >= 3:

            score += 4.0

        elif positive_matches >= 2:

            score += 2.0


        # --------------------------------------------------
        # NEGATIVE MATCH PENALTY
        # --------------------------------------------------

        if negative_matches >= 3:

            score -= 8.0

        elif negative_matches >= 2:

            score -= 5.0

        elif negative_matches >= 1:

            score -= 2.0


        # --------------------------------------------------
        # MOVIE QUALITY
        #
        # Rating has LOW influence.
        # Personal taste remains dominant.
        # --------------------------------------------------

        if movie.rating is not None:

            try:

                rating = float(
                    movie.rating
                )

                rating = max(
                    0.0,
                    min(rating, 10.0)
                )

                score += rating * 0.15

            except (
                ValueError,
                TypeError
            ):

                pass


        # --------------------------------------------------
        # SAVE RESULT
        # --------------------------------------------------

        scored_movies.append({

            "id": movie.id,

            "tmdb_id": movie.tmdb_id,

            "title": movie.title,

            "overview": movie.overview,

            "poster_path": movie.poster_path,

            "backdrop_path": movie.backdrop_path,

            "release_date": movie.release_date,

            "rating": movie.rating,

            "language": movie.language,

            "genres": movie.genres,

            "keywords": movie.keywords,

            "cast": movie.cast,

            "directors": movie.directors,

            "score": round(
                score,
                2
            )

        })


    # --------------------------------------------------
    # SORT BY PERSONAL TASTE
    # --------------------------------------------------

    scored_movies.sort(

        key=lambda movie: (

            movie["score"],

            movie["rating"] or 0

        ),

        reverse=True

    )


    # --------------------------------------------------
    # RETURN TOP 60
    # --------------------------------------------------

    recommendations_list = (
        scored_movies[:61]
    )


    # --------------------------------------------------
    # FINAL SAFETY CHECK
    #
    # NEVER RETURN A MOVIE THE USER ALREADY
    # RATED DURING THIS TEST.
    # --------------------------------------------------

    recommendations_list = [

        movie

        for movie in recommendations_list

        if movie["id"] not in swiped_movie_ids

    ]


    # --------------------------------------------------
    # RESPONSE
    # --------------------------------------------------

    return jsonify({

        "liked_count":
            len(liked_swipes),

        "very_liked_count":
            len(very_liked_swipes),

        "disliked_count":
            len(disliked_swipes),

        "not_seen_count":
            len(not_seen_swipes),

        "recommendations":
            recommendations_list,

        "retake_required": False,

        "no_matches": (
            len(recommendations_list) == 0
        ),

        "no_positive_signals": False,

        "all_disliked": False,

        "all_not_seen": False

    })




# ============================================================
# TMDB TEST
# ============================================================

@app.route("/test-tmdb")
def test_tmdb():

    try:

        data = get_popular_movies()

        movies = data.get(
            "results",
            []
        )

        return jsonify({

            "success": True,

            "total_results":
                data.get(
                    "total_results",
                    0
                ),

            "movies": [

                {

                    "title":
                        movie.get("title"),

                    "tmdb_id":
                        movie.get("id"),

                    "rating":
                        movie.get("vote_average"),

                }

                for movie in movies[:5]

            ],

        })

    except Exception as error:

        return jsonify({

            "success": False,

            "error": str(error),

        }), 500


# ============================================================
# DISCOVERY MOVIE SELECTION
# ============================================================

def build_discovery_movies():

    """
    Build a diverse set of movies for the discovery test.

    Movies used in previous tests are excluded so Retake Test
    gets a genuinely different pool.
    """

    # ========================================================
    # ALREADY USED
    # ========================================================

    used_movie_ids = (
        get_all_browser_used_movie_ids()
    )

    # ========================================================
    # DATABASE QUERY
    # ========================================================

    query = Movie.query

    if used_movie_ids:

        query = query.filter(
            ~Movie.id.in_(
                used_movie_ids
            )
        )

    available_movies = query.all()

    # ========================================================
    # FALLBACK
    #
    # If the database does not contain enough completely new
    # movies, use movies not used by the CURRENT test.
    #
    # This prevents the discovery page from becoming empty
    # after many tests when the database is small.
    # ========================================================

    if len(available_movies) < MAX_DISCOVERY_MOVIES:

        current_swiped_ids = (
            get_current_swiped_movie_ids()
        )

        fallback_query = Movie.query

        if current_swiped_ids:

            fallback_query = fallback_query.filter(
                ~Movie.id.in_(
                    current_swiped_ids
                )
            )

        available_movies = fallback_query.all()

    # ========================================================
    # SCORE BASIC QUALITY
    # ========================================================

    scored_movies = []

    for movie in available_movies:

        score = 0.0

        genre = first_metadata_value(
            movie.genres
        )

        director = first_metadata_value(
            movie.directors
        )

        language = (
            str(movie.language).strip().lower()
            if movie.language
            else None
        )

        year = get_movie_year(
            movie
        )

        # ----------------------------------------------------
        # Metadata quality
        # ----------------------------------------------------

        if genre:
            score += 2.0

        if director:
            score += 2.0

        if language:
            score += 1.0

        if year:
            score += 1.0

        # ----------------------------------------------------
        # Rating
        # ----------------------------------------------------

        rating = safe_rating(
            movie
        )

        if rating >= 8.0:

            score += 4.0

        elif rating >= 7.5:

            score += 3.0

        elif rating >= 6.5:

            score += 2.0

        elif rating >= 5.5:

            score += 1.0

        scored_movies.append(
            (
                score,
                movie,
            )
        )

    # ========================================================
    # QUALITY FIRST
    # ========================================================

    scored_movies.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    remaining = [
        movie
        for _, movie in scored_movies
    ]

    # ========================================================
    # DIVERSITY TRACKING
    # ========================================================

    selected_movies = []

    used_genres = set()

    used_directors = set()

    used_languages = set()

    used_years = set()

    # ========================================================
    # DIVERSE SELECTION
    # ========================================================

    while (
        remaining
        and len(selected_movies)
        < MAX_DISCOVERY_MOVIES
    ):

        best_movie = None

        best_score = float("-inf")

        best_metadata = None

        for movie in remaining:

            genre = first_metadata_value(
                movie.genres
            )

            director = first_metadata_value(
                movie.directors
            )

            language = (
                str(movie.language).strip().lower()
                if movie.language
                else None
            )

            year = get_movie_year(
                movie
            )

            diversity_score = 0.0

            # ------------------------------------------------
            # New genre
            # ------------------------------------------------

            if (
                genre
                and genre not in used_genres
            ):

                diversity_score += 10.0

            # ------------------------------------------------
            # New director
            # ------------------------------------------------

            if (
                director
                and director not in used_directors
            ):

                diversity_score += 4.0

            # ------------------------------------------------
            # New language
            # ------------------------------------------------

            if (
                language
                and language not in used_languages
            ):

                diversity_score += 3.0

            # ------------------------------------------------
            # New year
            # ------------------------------------------------

            if (
                year
                and year not in used_years
            ):

                diversity_score += 2.0

            # ------------------------------------------------
            # Quality
            # ------------------------------------------------

            diversity_score += min(
                safe_rating(movie),
                10.0
            )

            if diversity_score > best_score:

                best_score = (
                    diversity_score
                )

                best_movie = movie

                best_metadata = (
                    genre,
                    director,
                    language,
                    year,
                )

        if not best_movie:

            break

        selected_movies.append(
            best_movie
        )

        (
            genre,
            director,
            language,
            year,
        ) = best_metadata

        if genre:
            used_genres.add(
                genre
            )

        if director:
            used_directors.add(
                director
            )

        if language:
            used_languages.add(
                language
            )

        if year:
            used_years.add(
                year
            )

        remaining.remove(
            best_movie
        )

    # ========================================================
    # SECONDARY FILL
    #
    # If diversity rules left us with fewer than 20, fill
    # remaining slots from the best remaining movies.
    # ========================================================

    if len(selected_movies) < MAX_DISCOVERY_MOVIES:

        selected_ids = {
            movie.id
            for movie in selected_movies
        }

        for movie in remaining:

            if movie.id in selected_ids:
                continue

            selected_movies.append(
                movie
            )

            if (
                len(selected_movies)
                >= MAX_DISCOVERY_MOVIES
            ):
                break

    # ========================================================
    # FINAL QUALITY ORDER
    # ========================================================

    selected_movies.sort(
        key=lambda movie: (
            safe_rating(movie),
            movie.title or "",
        ),
        reverse=True,
    )

    return selected_movies[
        :MAX_DISCOVERY_MOVIES
    ]


# ============================================================
# DISCOVER
# ============================================================

@app.route("/discover")
def discover():

    # ========================================================
    # CREATE SESSION IF NECESSARY
    # ========================================================

    if not session.get("discovery_active"):

        session["sam_session_id"] = (
            str(uuid.uuid4())
        )

        session["discovery_active"] = True

        session["discovery_complete"] = False

        session["test_complete"] = False

        session.modified = True

    session_id = (
        session["sam_session_id"]
    )

    # ========================================================
    # CURRENT SWIPES
    # ========================================================

    previous_swipes = Swipe.query.filter_by(
        session_id=session_id
    ).all()

    swipe_count = len(
        previous_swipes
    )

    # ========================================================
    # COMPLETED
    # ========================================================

    if swipe_count >= MAX_DISCOVERY_MOVIES:

        session["discovery_complete"] = True

        session["test_complete"] = True

        session.modified = True

        return render_template(
            "discover.html",
            movies=[],
            test_complete=True,
            swipe_count=swipe_count,
            remaining=0,
        )

    # ========================================================
    # BUILD MOVIES
    # ========================================================

    selected_movies = (
        build_discovery_movies()
    )

    # ========================================================
    # CONVERT TO TEMPLATE DATA
    # ========================================================

    movie_data = [
        movie_to_dict(movie)
        for movie in selected_movies
    ]

    # ========================================================
    # RENDER
    # ========================================================

    return render_template(

        "discover.html",

        movies=movie_data,

        test_complete=False,

        swipe_count=swipe_count,

        remaining=max(
            0,
            MAX_DISCOVERY_MOVIES
            - swipe_count,
        ),

    )


# ============================================================
# DEBUG / STATUS ROUTE
# ============================================================

@app.route("/api/test-status")
def test_status():

    session_id = get_current_session_id()

    if not session_id:

        return jsonify({

            "active": False,

            "session_id": None,

            "swipe_count": 0,

            "remaining":
                MAX_DISCOVERY_MOVIES,

            "complete": False,

        })

    swipes = Swipe.query.filter_by(
        session_id=session_id
    ).all()

    count = len(swipes)

    return jsonify({

        "active":
            True,

        "session_id":
            session_id,

        "swipe_count":
            count,

        "remaining":
            max(
                0,
                MAX_DISCOVERY_MOVIES - count
            ),

        "complete":
            count >= MAX_DISCOVERY_MOVIES,

        "all_disliked":
            is_all_dislike_test(swipes),

        "used_movie_count":
            len(
                get_all_browser_used_movie_ids()
            ),

    })


# ============================================================
# CLEAR CURRENT TEST
# ============================================================

@app.route("/api/clear-current-test", methods=["POST"])
def clear_current_test():

    session_id = get_current_session_id()

    if not session_id:

        return jsonify({
            "success": True,
            "deleted": 0,
        })

    swipes = Swipe.query.filter_by(
        session_id=session_id
    ).all()

    deleted = len(swipes)

    for swipe in swipes:

        db.session.delete(
            swipe
        )

    db.session.commit()

    session["discovery_complete"] = False

    session["test_complete"] = False

    session.modified = True

    return jsonify({

        "success": True,

        "deleted": deleted,

    })









@app.route("/credits")
def credits():
    return render_template("credits.html")


# ============================================================
# APPLICATION START
# ============================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )