import sqlite3


conn = sqlite3.connect("instance/sam.db")
cursor = conn.cursor()


print("DATABASE CONNECTED")
print()


# --------------------------------------------------
# TOTAL MOVIES
# --------------------------------------------------

cursor.execute(
    "SELECT COUNT(*) FROM movies"
)

total = cursor.fetchone()[0]

print("TOTAL MOVIES:", total)
print()


# --------------------------------------------------
# FIND SHAWSHANK
# --------------------------------------------------

cursor.execute(
    """
    SELECT
        title,
        genres,
        directors,
        "cast",
        keywords
    FROM movies
    WHERE title = ?
    """,
    ("The Shawshank Redemption",)
)

row = cursor.fetchone()


if row is None:

    print("SHAWSHANK NOT FOUND")

else:

    print("SHAWSHANK FOUND")
    print("------------------------------")

    print("TITLE:")
    print(row[0])

    print()

    print("GENRES:")
    print(row[1])

    print()

    print("DIRECTORS:")
    print(row[2])

    print()

    print("CAST:")
    print(row[3])

    print()

    print("KEYWORDS:")
    print(row[4])


print()


# --------------------------------------------------
# MISSING METADATA
# --------------------------------------------------

cursor.execute(
    """
    SELECT COUNT(*)
    FROM movies
    WHERE
        genres IS NULL
        OR directors IS NULL
        OR "cast" IS NULL
        OR keywords IS NULL
    """
)

missing = cursor.fetchone()[0]

print(
    "MOVIES WITH MISSING METADATA:",
    missing
)

print()


# --------------------------------------------------
# FIRST 5 MOVIES
# --------------------------------------------------

cursor.execute(
    """
    SELECT
        title,
        genres,
        directors,
        "cast",
        keywords
    FROM movies
    LIMIT 5
    """
)

rows = cursor.fetchall()


print("FIRST 5 MOVIES")
print("------------------------------")


for movie in rows:

    print()
    print("TITLE:", movie[0])
    print("GENRES:", movie[1])
    print("DIRECTORS:", movie[2])
    print("CAST:", movie[3])
    print("KEYWORDS:", movie[4])


conn.close()


print()
print("DONE")