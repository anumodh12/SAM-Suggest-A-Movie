let currentMovieIndex = 0;
let isChoosingMovie = false;

const movieCard = document.getElementById("movie-card");

const movieTitle = document.getElementById("movie-title");
const movieRating = document.getElementById("movie-rating");
const movieMeta = document.getElementById("movie-meta");
const movieDescription = document.getElementById("movie-description");
const moviePoster = document.getElementById("movie-poster");

const likeButton = document.getElementById("like-button");
const dislikeButton = document.getElementById("dislike-button");


// --------------------------------------------------
// MOVIE DISPLAY
// --------------------------------------------------

function showMovie() {

    // No movies available
    if (!movies || movies.length === 0) {

        movieTitle.textContent = "You're all caught up!";
        movieRating.textContent = "";
        movieMeta.textContent = "";

        movieDescription.textContent =
            "You've gone through all the movies. SAM will use your choices to recommend something for you.";

        moviePoster.style.backgroundImage = "none";

        likeButton.style.display = "none";
        dislikeButton.style.display = "none";

        return;
    }


    // All movies in this batch have been shown
    if (currentMovieIndex >= movies.length) {

        movieTitle.textContent = "You're all caught up!";
        movieRating.textContent = "";
        movieMeta.textContent = "";

        movieDescription.textContent =
            "You've gone through all the movies. SAM will use your choices to recommend something for you.";

        moviePoster.style.backgroundImage = "none";

        likeButton.style.display = "none";
        dislikeButton.style.display = "none";

        return;
    }


    const movie = movies[currentMovieIndex];


    // Make sure buttons are visible
    likeButton.style.display = "";
    dislikeButton.style.display = "";


    // --------------------------------------------------
    // TITLE
    // --------------------------------------------------

    movieTitle.textContent =
        movie.title || "Unknown Movie";


    // --------------------------------------------------
    // RATING
    // --------------------------------------------------

    movieRating.textContent =
        movie.rating !== null &&
        movie.rating !== undefined
            ? Number(movie.rating).toFixed(1)
            : "N/A";


    // --------------------------------------------------
    // RELEASE YEAR
    // --------------------------------------------------

    let year = "";

    if (movie.release_date) {

        year = movie.release_date.substring(0, 4);
    }


    movieMeta.textContent =
        year || "Release date unknown";


    // --------------------------------------------------
    // DESCRIPTION
    // --------------------------------------------------

    movieDescription.textContent =
        movie.overview ||
        "No description available.";


    // --------------------------------------------------
    // POSTER
    // --------------------------------------------------

    if (movie.poster_path) {

        moviePoster.style.backgroundImage =
            `url("https://image.tmdb.org/t/p/w500${movie.poster_path}")`;

        moviePoster.style.backgroundSize = "cover";
        moviePoster.style.backgroundPosition = "center";

    } else {

        moviePoster.style.backgroundImage = "none";
    }
}


// --------------------------------------------------
// SAVE SWIPE
// --------------------------------------------------

async function chooseMovie(choice) {

    // Prevent double clicks
    if (isChoosingMovie) {
        return;
    }


    // Make sure there is a movie
    if (!movies || currentMovieIndex >= movies.length) {
        return;
    }


    isChoosingMovie = true;


    const movie = movies[currentMovieIndex];


    console.log(
        "Choosing movie:",
        movie.title,
        "Action:",
        choice
    );


    // --------------------------------------------------
    // ANIMATION
    // --------------------------------------------------

    if (choice === "like") {

        movieCard.classList.add("swipe-right");

    } else if (choice === "dislike") {

        movieCard.classList.add("swipe-left");

    } else if (choice === "very-like") {

        movieCard.classList.add("swipe-up");

    } else if (choice === "not-seen") {

        movieCard.classList.add("swipe-down");
    }


    // --------------------------------------------------
    // SEND TO FLASK
    // --------------------------------------------------

    try {

        const response = await fetch(
            "/api/swipe",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    movie_id: movie.id,
                    action: choice
                })
            }
        );


        const data = await response.json();


        console.log(
            "Swipe response:",
            data
        );


        // --------------------------------------------------
        // SERVER REJECTED SWIPE
        // --------------------------------------------------

        if (!response.ok || !data.success) {

            console.error(
                "Swipe failed:",
                data.error || data.message
            );


            resetCard();


            isChoosingMovie = false;

            return;
        }


        // --------------------------------------------------
        // TEST COMPLETE
        // --------------------------------------------------

        if (data.test_complete === true) {

            console.log(
                "Discovery test complete."
            );


            setTimeout(() => {

                window.location.href =
                    "/recommendations-page";

            }, 450);


            return;
        }


        // --------------------------------------------------
        // MOVE TO NEXT MOVIE
        // --------------------------------------------------

        setTimeout(() => {

            // Remove animation
            movieCard.classList.remove(
                "swipe-left",
                "swipe-right",
                "swipe-up",
                "swipe-down"
            );


            // Reset transform
            movieCard.style.transform = "";


            // IMPORTANT:
            // Advance to the next movie
            currentMovieIndex++;


            console.log(
                "Moving to movie index:",
                currentMovieIndex
            );


            // Display next movie
            showMovie();


            // Allow another swipe
            isChoosingMovie = false;

        }, 450);


    } catch (error) {

        console.error(
            "Failed to save swipe:",
            error
        );


        resetCard();


        isChoosingMovie = false;
    }
}


// --------------------------------------------------
// RESET CARD AFTER FAILED REQUEST
// --------------------------------------------------

function resetCard() {

    movieCard.classList.remove(
        "swipe-left",
        "swipe-right",
        "swipe-up",
        "swipe-down"
    );

    movieCard.style.transform = "";
}


// --------------------------------------------------
// BUTTON EVENTS
// --------------------------------------------------

likeButton.addEventListener(
    "click",
    () => chooseMovie("like")
);


dislikeButton.addEventListener(
    "click",
    () => chooseMovie("dislike")
);


// --------------------------------------------------
// INITIAL MOVIE
// --------------------------------------------------

showMovie();




function showTestComplete() {

    movieCard.innerHTML = `

        <div class="test-complete">

            <div class="test-complete-icon">
                ✓
            </div>

            <p class="eyebrow">
                TASTE PROFILE COMPLETE
            </p>

            <h2>
                SAM has learned
                your taste.
            </h2>

            <p>
                You've rated enough movies for SAM
                to build your personalized recommendations.
            </p>

            <button
                class="recommendation-button"
                onclick="window.location.href='/recommendations-page'"
            >
                See My Recommendations →
            </button>

        </div>

    `;


    likeButton.style.display = "none";
    dislikeButton.style.display = "none";
}






// --------------------------------------------------
// BUTTONS
// --------------------------------------------------

likeButton.addEventListener(
    "click",
    () => chooseMovie("like")
);

dislikeButton.addEventListener(
    "click",
    () => chooseMovie("dislike")
);


// --------------------------------------------------
// DRAGGING
// --------------------------------------------------

let isDragging = false;

let startX = 0;
let startY = 0;

let currentX = 0;
let currentY = 0;


// Mouse
movieCard.addEventListener("mousedown", startDrag);

// Touch
movieCard.addEventListener("touchstart", startDrag, {
    passive: true
});


function startDrag(event) {

    if (currentMovieIndex >= movies.length) {
        return;
    }

    isDragging = true;

    movieCard.classList.add("dragging");


    if (event.type === "touchstart") {

        startX = event.touches[0].clientX;
        startY = event.touches[0].clientY;

    } else {

        startX = event.clientX;
        startY = event.clientY;
    }

    currentX = 0;
    currentY = 0;
}


// Mouse movement
document.addEventListener("mousemove", dragMove);

// Touch movement
document.addEventListener("touchmove", dragMove, {
    passive: false
});


function dragMove(event) {

    if (!isDragging) {
        return;
    }


    let x;
    let y;


    if (event.type === "touchmove") {

        x = event.touches[0].clientX;
        y = event.touches[0].clientY;

        event.preventDefault();

    } else {

        x = event.clientX;
        y = event.clientY;
    }


    currentX = x - startX;
    currentY = y - startY;


    const rotation =
        currentX * 0.05;


    movieCard.style.transform =
        `translate(${currentX}px, ${currentY}px) rotate(${rotation}deg)`;
}


// Mouse release
document.addEventListener("mouseup", endDrag);

// Touch release
document.addEventListener("touchend", endDrag);


function endDrag() {

    if (!isDragging) {
        return;
    }

    isDragging = false;

    movieCard.classList.remove("dragging");


    const horizontalDistance =
        Math.abs(currentX);

    const verticalDistance =
        Math.abs(currentY);


    const threshold = 120;


    // Not far enough → return to center

    if (
        horizontalDistance < threshold &&
        verticalDistance < threshold
    ) {

        movieCard.style.transform = "";

        return;
    }


    // Determine dominant direction

    if (horizontalDistance > verticalDistance) {

        if (currentX > 0) {

            // →
            chooseMovie("like");

        } else {

            // ←
            chooseMovie("dislike");
        }

    } else {

        if (currentY < 0) {

            // ↑
            chooseMovie("very-like");

        } else {

            // ↓
            chooseMovie("not-seen");
        }
    }


    movieCard.style.transform = "";
}


// --------------------------------------------------
// INITIAL PAGE STATE
// --------------------------------------------------

if (testComplete) {

    showTestComplete();

} else {

    showMovie();

}