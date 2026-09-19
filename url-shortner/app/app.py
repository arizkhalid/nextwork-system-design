import os
import string

from flask import Flask, request, redirect, jsonify
import redis
import psycopg2

app = Flask(__name__)

# The 62 characters short codes are built from
ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase

cache = redis.Redis(
    host=os.environ.get("REDIS_HOST", "redis"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True,
)


def get_db():
    return psycopg2.connect(
        host=os.environ.get("POSTGRES_HOST", "db"),
        database=os.environ.get("POSTGRES_DB", "urlshortener"),
        user=os.environ.get("POSTGRES_USER", "postgres"),
        password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
    )


def base62_encode(num):
    """Convert a database ID into a short alphanumeric string."""
    if num == 0:
        return ALPHABET[0]
    result = []
    while num > 0:
        num, remainder = divmod(num, 62)
        result.append(ALPHABET[remainder])
    return "".join(reversed(result))


def base62_decode(code):
    """Convert a short code back into the original database ID."""
    num = 0
    for char in code:
        num = num * 62 + ALPHABET.index(char)
    return num

@app.route("/shorten", methods=["POST"])
def shorten_url():
    url = request.get_json()["url"]
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM urls WHERE long_url = %s", (url,))
    row = cur.fetchone()
    if row is not None:
        res_id = row[0]
    else:
        cur.execute("INSERT INTO urls (long_url) VALUES (%s) RETURNING id", (url,))
        res_id = cur.fetchone()[0]
    conn.commit()
    res = base62_encode(res_id)
    cur.close()
    conn.close()
    return res

@app.route("/<id>")
def listener(id):
    primary_key = base62_decode(id) 
    if res := cache.get(id):
        return redirect(res, code=302) 
        
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT long_url FROM urls WHERE id = %s", (primary_key, ))
    res = cur.fetchone()[0]
    cache.set(id, res, ex=3600)
    return redirect(res, code=302)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
