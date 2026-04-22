from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
from boto3.dynamodb.conditions import Key, Attr
from config import LOGIN_TABLE, MUSIC_TABLE, SUBSCRIPTIONS_TABLE, S3_BUCKET, AWS_REGION

app = Flask(__name__)
CORS(app)

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)

login_table = dynamodb.Table(LOGIN_TABLE)
music_table = dynamodb.Table(MUSIC_TABLE)
subscriptions_table = dynamodb.Table(SUBSCRIPTIONS_TABLE)


def get_image_url(image_name: str) -> str:
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": S3_BUCKET, "Key": image_name},
        ExpiresIn=3600
    )


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
    title = request.args.get("title", "").strip()
    year = request.args.get("year", "").strip()
    artist = request.args.get("artist", "").strip()
    album = request.args.get("album", "").strip()

    if not any([title, year, artist, album]):
        return jsonify({"success": False, "message": "At least one field must be completed"}), 400

    response = music_table.scan()
    items = response.get("Items", [])

    filtered = []
    for item in items:
        if title and item.get("title", "").strip().lower() != title.lower():
            continue
        if year and str(item.get("year", "")).strip() != str(year):
            continue
        if artist and item.get("artist", "").strip().lower() != artist.lower():
            continue
        if album and item.get("album", "").strip().lower() != album.lower():
            continue

        item["image_url"] = get_image_url(item["img_url"])
        item["song_id"] = f"{item['artist']}#{item['title']}#{item['album']}"
        filtered.append(item)

    if not filtered:
        return jsonify({
            "success": False,
            "message": "No result is retrieved. Please query again",
            "songs": []
        })

    return jsonify({"success": True, "songs": filtered})

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
        item["image_url"] = get_image_url(item["img_url"])

    return jsonify({"success": True, "subscriptions": items})


@app.route("/subscriptions", methods=["POST"])
def add_subscription():
    data = request.get_json()
    email = data.get("email", "").strip()
    artist = data.get("artist", "").strip()
    title = data.get("title", "").strip()
    album = data.get("album", "").strip()
    year = str(data.get("year", "")).strip()
    img_url = data.get("img_url", "").strip()

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
    app.run(debug=True, port=5000)