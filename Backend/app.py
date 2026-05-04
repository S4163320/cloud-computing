from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
from boto3.dynamodb.conditions import Key
from config import LOGIN_TABLE, MUSIC_TABLE, SUBSCRIPTIONS_TABLE, S3_BUCKET, AWS_REGION

app = Flask(__name__)
CORS(app)

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)

login_table = dynamodb.Table(LOGIN_TABLE)
music_table = dynamodb.Table(MUSIC_TABLE)
subscriptions_table = dynamodb.Table(SUBSCRIPTIONS_TABLE)


def _looks_like_s3_key(value: str) -> bool:
    if not value:
        return False
    v = value.strip()
    if not v:
        return False
    # If the loader accidentally stored a full URL here, don't try to presign it.
    return not (v.startswith("http://") or v.startswith("https://"))


def _extract_image_key(item: dict) -> str:
    """Return the S3 object key for this item (or empty string if missing)."""
    for field in ("image_key", "s3_key", "img_url"):
        val = item.get(field)
        if isinstance(val, str) and _looks_like_s3_key(val):
            return val.strip()
    return ""


def get_image_url(image_key: str) -> str:
    """Generate presigned URL for an S3 object key (or empty string)."""
    if not _looks_like_s3_key(image_key):
        return ""
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": image_key.strip()},
            ExpiresIn=3600,
        )
    except Exception:
        # Never crash the endpoint due to missing/invalid image key.
        return ""


def _paginated_query(**kwargs):
    """Read all pages from Query (indexed access is cheaper than a full-table Scan)."""
    items = []
    while True:
        resp = music_table.query(**kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return items


def _paginated_scan():
    """Fallback when no key pattern maps to the table PK/SK, LSI, or GSI."""
    items = []
    kwargs = {}
    while True:
        resp = music_table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        kwargs["ExclusiveStartKey"] = lek
    return items


def _apply_song_filters(items, title, year, artist, album):
    """AND semantics for optional fields (same behaviour as the previous Scan loop)."""
    filtered = []
    title_norm = str(title).strip().lower()
    artist_norm = str(artist).strip().lower()
    album_norm = str(album).strip().lower()
    year_norm = str(year).strip()

    for item in items:
        item_title = str(item.get("title", "")).strip().lower()
        item_artist = str(item.get("artist", "")).strip().lower()
        item_album = str(item.get("album", "")).strip().lower()
        item_year = str(item.get("year", "")).strip()

        if title_norm and item_title != title_norm:
            continue
        if year_norm and item_year != year_norm:
            continue
        if artist_norm and item_artist != artist_norm:
            continue
        if album_norm and item_album != album_norm:
            continue
        filtered.append(item)
    return filtered


def _enrich_songs(items):
    out = []
    for item in items:
        row = dict(item)
        image_key = _extract_image_key(row)
        row["image_url"] = get_image_url(image_key)
        row["song_id"] = f"{row['artist']}#{row['title']}#{row['album']}"
        out.append(row)
    return out


@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email", "").strip()
    password = data.get("password", "").strip()

    if not email or not password:
        return jsonify({"success": False, "message": "email or password is invalid"}), 400

    response = login_table.get_item(Key={"email": email})
    user = response.get("Item")

    if not user or user.get("password") != password:
        return jsonify({"success": False, "message": "email or password is invalid"}), 401

    return jsonify({
        "success": True,
        "email": user["email"],
        "user_name": user["user_name"]
    })


@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    email = data.get("email", "").strip()
    user_name = data.get("user_name", "").strip()
    password = data.get("password", "").strip()

    if not email or not user_name or not password:
        return jsonify({"success": False, "message": "All fields are required"}), 400

    existing = login_table.get_item(Key={"email": email}).get("Item")
    if existing:
        return jsonify({"success": False, "message": "The email already exists"}), 409

    login_table.put_item(Item={
        "email": email,
        "user_name": user_name,
        "password": password
    })

    return jsonify({"success": True, "message": "Registration successful"})


@app.route("/songs", methods=["GET"])
def query_songs():
    # 1. Get raw inputs (for exact DynamoDB index matches)
    artist_raw = request.args.get("artist", "").strip()
    year_raw = request.args.get("year", "").strip()
    title_raw = request.args.get("title", "").strip()
    album_raw = request.args.get("album", "").strip()

    # 2. Normalize for Python filtering (partial/case-insensitive match)
    artist_norm = artist_raw.lower()
    album_norm = album_raw.lower()
    title_norm = title_raw.lower()

    if not any([artist_raw, year_raw, title_raw, album_raw]):
        return jsonify({"success": False, "message": "At least one field must be completed"}), 400

    items = []
    
    # Try high-speed Query first if keys are provided
    try:
        if artist_raw and year_raw:
            items = _paginated_query(
                IndexName="artist-year-index",
                KeyConditionExpression=Key("artist").eq(artist_raw) & Key("year").eq(year_raw)
            )
        elif album_raw:
            items = _paginated_query(
                IndexName="album-year-index",
                KeyConditionExpression=Key("album").eq(album_raw)
            )
        elif artist_raw:
            items = _paginated_query(
                KeyConditionExpression=Key("artist").eq(artist_raw)
            )
    except Exception:
        pass # If query fails, we fall through to Scan

    # 3. If Query found nothing (possibly due to partial name like 'Taylor'), 
    # use Scan to find the partial match.
    if not items:
        items = _paginated_scan()

    # 4. Apply the final Python filter (Handles partial strings and case-insensitivity)
    filtered = []
    for item in items:
        db_title = str(item.get("title", "")).lower()
        db_artist = str(item.get("artist", "")).lower()
        db_album = str(item.get("album", "")).lower()
        db_year = str(item.get("year", ""))

        if title_norm and title_norm not in db_title: continue
        if artist_norm and artist_norm not in db_artist: continue
        if album_norm and album_norm not in db_album: continue
        if year_raw and year_raw != db_year: continue
        
        filtered.append(item)

    enriched = _enrich_songs(filtered)
    
    if not enriched:
        return jsonify({
            "success": False,
            "message": "No result is retrieved. Please query again",
            "songs": []
        })

    return jsonify({"success": True, "songs": enriched})


@app.route("/subscriptions", methods=["GET"])
def get_subscriptions():
    email = request.args.get("email", "").strip()
    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400

    response = subscriptions_table.query(
        KeyConditionExpression=Key("email").eq(email)
    )

    items = response.get("Items", [])
    for item in items:
        image_key = _extract_image_key(item)
        item["image_url"] = get_image_url(image_key)

    return jsonify({"success": True, "subscriptions": items})


@app.route("/subscriptions", methods=["POST"])
def add_subscription():
    data = request.get_json()
    print("POST /subscriptions called")
    print("POST /subscriptions payload:", data)
    email = data.get("email", "").strip()
    artist = data.get("artist", "").strip()
    title = data.get("title", "").strip()
    album = data.get("album", "").strip()
    year = str(data.get("year", "")).strip()
    img_url = (
        data.get("img_url", "")
        or data.get("image_key", "")
        or data.get("s3_key", "")
    ).strip()

    if not all([email, artist, title, album, year, img_url]):
        return jsonify({"success": False, "message": "Missing subscription data"}), 400

    song_id = f"{artist}#{title}#{album}"

    subscriptions_table.put_item(Item={
        "email": email,
        "song_id": song_id,
        "artist": artist,
        "title": title,
        "album": album,
        "year": year,
        "img_url": img_url
    })

    return jsonify({"success": True, "message": "Subscribed successfully"})


@app.route("/subscriptions/<email>/<path:song_id>", methods=["DELETE"])
def remove_subscription(email, song_id):
    subscriptions_table.delete_item(
        Key={
            "email": email,
            "song_id": song_id
        }
    )
    return jsonify({"success": True, "message": "Removed successfully"})


if __name__ == "__main__":
   app.run(host="0.0.0.0", debug=True, port=5000)