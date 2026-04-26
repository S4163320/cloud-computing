"""
Standalone Lambda backend for API Gateway (REST API, Lambda proxy integration).

Important:
- This file is intentionally separate from the EC2 Flask backend.
- Do not import Backend/app.py or Backend/config.py to avoid coupling.
- Query is used first for indexed access patterns; Scan is only fallback.
"""

import json
from urllib.parse import unquote

import boto3
from boto3.dynamodb.conditions import Key

# Copied constants (kept local to Lambda to avoid touching EC2 backend files).
AWS_REGION = "us-east-1"
LOGIN_TABLE = "login_v2"
MUSIC_TABLE = "music_v4"
SUBSCRIPTIONS_TABLE = "subscriptions"
S3_BUCKET = "music-images-33"

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS",
}

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)

login_table = dynamodb.Table(LOGIN_TABLE)
music_table = dynamodb.Table(MUSIC_TABLE)
subscriptions_table = dynamodb.Table(SUBSCRIPTIONS_TABLE)


def _response(status_code, data):
    return {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
        "body": json.dumps(data),
    }


def _parse_body(event):
    raw_body = event.get("body")
    if not raw_body:
        return {}
    if isinstance(raw_body, dict):
        return raw_body
    try:
        return json.loads(raw_body)
    except Exception:
        return {}


def _get_query_params(event):
    return event.get("queryStringParameters") or {}


def _norm_text(value):
    return str(value or "").strip().lower()


def _norm_year(value):
    return str(value or "").strip()


def _looks_like_s3_key(value):
    if not value:
        return False
    v = str(value).strip()
    if not v:
        return False
    return not (v.startswith("http://") or v.startswith("https://"))


def _extract_image_key(item):
    # Prefer explicit key fields, then img_url/image_url when they look like keys.
    for field in ("image_key", "s3_key", "img_url", "image_url"):
        val = item.get(field)
        if isinstance(val, str) and _looks_like_s3_key(val):
            return val.strip()
    return ""


def _safe_presigned_url(image_key):
    if not _looks_like_s3_key(image_key):
        return ""
    if not S3_BUCKET:
        return ""
    try:
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": S3_BUCKET, "Key": image_key},
            ExpiresIn=3600,
        )
    except Exception:
        return ""


def _paginated_query(**kwargs):
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
    title_norm = _norm_text(title)
    artist_norm = _norm_text(artist)
    album_norm = _norm_text(album)
    year_norm = _norm_year(year)

    filtered = []
    for item in items:
        item_title = _norm_text(item.get("title", ""))
        item_artist = _norm_text(item.get("artist", ""))
        item_album = _norm_text(item.get("album", ""))
        item_year = _norm_year(item.get("year", ""))

        if title_norm and item_title != title_norm:
            continue
        if artist_norm and item_artist != artist_norm:
            continue
        if album_norm and item_album != album_norm:
            continue
        if year_norm and item_year != year_norm:
            continue

        filtered.append(item)
    return filtered


def _enrich_songs(items):
    out = []
    for item in items:
        row = dict(item)
        image_key = _extract_image_key(row)

        # Keep img_url for frontend subscribe payload compatibility.
        if image_key and not row.get("img_url"):
            row["img_url"] = image_key

        # Keep existing URL if already present; otherwise generate presigned URL.
        existing_image_url = row.get("image_url", "")
        if isinstance(existing_image_url, str) and existing_image_url.startswith(("http://", "https://")):
            row["image_url"] = existing_image_url
        else:
            row["image_url"] = _safe_presigned_url(image_key)

        row["song_id"] = f"{row.get('artist', '')}#{row.get('title', '')}#{row.get('album', '')}"
        out.append(row)
    return out


def _parse_subscriptions_delete_path(path, path_params):
    # Primary: API Gateway path parameters.
    email = ""
    song_id = ""
    if path_params:
        email = path_params.get("email", "") or path_params.get("proxy", "")
        song_id = path_params.get("songId", "") or path_params.get("song_id", "")

    # Fallback: manual parsing from full path.
    # Expected path: /subscriptions/{email}/{songId}
    # Song IDs can contain encoded special characters, so after "subscriptions"
    # we treat next segment as email and join all remaining segments as song_id.
    if not email or not song_id:
        parts = [p for p in path.split("/") if p]
        if "subscriptions" in parts:
            idx = parts.index("subscriptions")
            if len(parts) > idx + 2:
                email = parts[idx + 1]
                song_id = "/".join(parts[idx + 2 :])

    return unquote(email), unquote(song_id)


def _route_matches(path, suffix):
    # Supports direct /login and staged paths like /prod/login.
    return path == suffix or path.endswith(suffix)


def _handle_login(event):
    data = _parse_body(event)
    email = str(data.get("email", "")).strip()
    password = str(data.get("password", "")).strip()

    if not email or not password:
        return _response(400, {"success": False, "message": "email or password is invalid"})

    user = login_table.get_item(Key={"email": email}).get("Item")
    if not user or user.get("password") != password:
        return _response(401, {"success": False, "message": "email or password is invalid"})

    return _response(
        200,
        {"success": True, "email": user.get("email"), "user_name": user.get("user_name")},
    )


def _handle_register(event):
    data = _parse_body(event)
    email = str(data.get("email", "")).strip()
    user_name = str(data.get("user_name", "")).strip()
    password = str(data.get("password", "")).strip()

    if not email or not user_name or not password:
        return _response(400, {"success": False, "message": "All fields are required"})

    existing = login_table.get_item(Key={"email": email}).get("Item")
    if existing:
        return _response(409, {"success": False, "message": "The email already exists"})

    login_table.put_item(
        Item={"email": email, "user_name": user_name, "password": password}
    )
    return _response(200, {"success": True, "message": "Registration successful"})


def _handle_songs(event):
    params = _get_query_params(event)

    # Keep raw values for Query (DynamoDB keys are case-sensitive).
    title_raw = str(params.get("title", "")).strip()
    year_raw = str(params.get("year", "")).strip()
    artist_raw = str(params.get("artist", "")).strip()
    album_raw = str(params.get("album", "")).strip()

    # Normalize for Python-side filtering.
    title = _norm_text(title_raw)
    artist = _norm_text(artist_raw)
    album = _norm_text(album_raw)
    year = _norm_year(year_raw)

    if not any([title, year, artist, album]):
        return _response(
            400, {"success": False, "message": "At least one field must be completed"}
        )

    # Query first for optimized indexed access patterns.
    items = []
    used_query = False

    if artist_raw and year_raw:
        items = _paginated_query(
            IndexName="artist-year-index",
            KeyConditionExpression=Key("artist").eq(artist_raw) & Key("year").eq(year_raw),
        )
        used_query = True
    elif album_raw and year_raw:
        items = _paginated_query(
            IndexName="album-year-index",
            KeyConditionExpression=Key("album").eq(album_raw) & Key("year").eq(year_raw),
        )
        used_query = True
    elif artist_raw:
        items = _paginated_query(KeyConditionExpression=Key("artist").eq(artist_raw))
        used_query = True
    elif album_raw:
        items = _paginated_query(
            IndexName="album-year-index",
            KeyConditionExpression=Key("album").eq(album_raw),
        )
        used_query = True
    else:
        # title-only / year-only (or no indexed key) fallback.
        items = _paginated_scan()

    # Case mismatch fallback: keep Query for marks, Scan only when Query yields no rows.
    if used_query and not items:
        items = _paginated_scan()

    filtered = _apply_song_filters(items, title, year, artist, album)
    enriched = _enrich_songs(filtered)

    if not enriched:
        return _response(
            200,
            {
                "success": False,
                "message": "No result is retrieved. Please query again",
                "songs": [],
            },
        )
    return _response(200, {"success": True, "songs": enriched})


def _handle_get_subscriptions(event):
    params = _get_query_params(event)
    email = str(params.get("email", "")).strip()
    if not email:
        return _response(400, {"success": False, "message": "Email is required"})

    response = subscriptions_table.query(KeyConditionExpression=Key("email").eq(email))
    items = response.get("Items", [])
    items = _enrich_songs(items)
    return _response(200, {"success": True, "subscriptions": items})


def _handle_post_subscriptions(event):
    data = _parse_body(event)
    email = str(data.get("email", "")).strip()
    artist = str(data.get("artist", "")).strip()
    title = str(data.get("title", "")).strip()
    album = str(data.get("album", "")).strip()
    year = _norm_year(data.get("year", ""))

    # Accept either S3 key or full URL for image field. Do not reject if caller
    # sends image_url as a presigned/full http(s) URL.
    img_url = str(
        data.get("img_url")
        or data.get("image_url")
        or data.get("image_key")
        or data.get("s3_key")
        or ""
    ).strip()

    if not all([email, artist, title, album, year, img_url]):
        return _response(400, {"success": False, "message": "Missing subscription data"})

    song_id = f"{artist}#{title}#{album}"
    subscriptions_table.put_item(
        Item={
            "email": email,
            "song_id": song_id,
            "artist": artist,
            "title": title,
            "album": album,
            "year": year,
            "img_url": img_url,
        }
    )
    return _response(200, {"success": True, "message": "Subscribed successfully"})


def _handle_delete_subscription(event):
    path = event.get("path", "") or ""
    path_params = event.get("pathParameters") or {}
    email, song_id = _parse_subscriptions_delete_path(path, path_params)

    if not email or not song_id:
        return _response(400, {"success": False, "message": "Invalid subscription path"})

    subscriptions_table.delete_item(Key={"email": email, "song_id": song_id})
    return _response(200, {"success": True, "message": "Removed successfully"})


def lambda_handler(event, context):
    method = (event.get("httpMethod") or "").upper()
    path = event.get("path") or ""

    if method == "OPTIONS":
        return _response(200, {"success": True})

    try:
        if method == "POST" and _route_matches(path, "/login"):
            return _handle_login(event)

        if method == "POST" and _route_matches(path, "/register"):
            return _handle_register(event)

        if method == "GET" and _route_matches(path, "/songs"):
            return _handle_songs(event)

        if method == "GET" and _route_matches(path, "/subscriptions"):
            return _handle_get_subscriptions(event)

        if method == "POST" and _route_matches(path, "/subscriptions"):
            return _handle_post_subscriptions(event)

        if method == "DELETE" and "/subscriptions/" in path:
            return _handle_delete_subscription(event)

        return _response(404, {"success": False, "message": "Not found"})
    except Exception as exc:
        # Keep frontend contract simple while exposing debug message.
        return _response(500, {"success": False, "message": str(exc)})
