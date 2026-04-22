import json
import boto3
import requests

# ----------------------------
# AWS CONFIGURATION
# ----------------------------
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

TABLE_NAME = "music_v3"
BUCKET_NAME = "music-images-33"

table = dynamodb.Table(TABLE_NAME)

print("Script started: Loading dataset and processing records")

# ----------------------------
# LOAD JSON DATA
# ----------------------------
with open("2026a2_songs.json", "r") as file:
    data = json.load(file)

songs = data["songs"]

print(f"Total records found in dataset: {len(songs)}")

# ----------------------------
# PROCESS EACH SONG
# ----------------------------
for i, song in enumerate(songs):

    print(f"Processing record {i+1}: {song.get('title')}")

    if not song.get("artist") or not song.get("title") or not song.get("album"):
        print("Skipping invalid record due to missing attributes")
        continue

    year = str(song["year"])

    image_url = song["img_url"]
    image_name = image_url.split("/")[-1]

    # New unique sort-key value
    title_album = song["title"] + "#" + song["album"]

    try:
        image_data = requests.get(image_url, timeout=10).content

        try:
            s3.head_object(Bucket=BUCKET_NAME, Key=image_name)
            print("Image already exists in S3, skipping upload")
        except:
            s3.put_object(
                Bucket=BUCKET_NAME,
                Key=image_name,
                Body=image_data,
                ContentType="image/jpeg"
            )
            print("Image uploaded to S3")

        item = {
            "artist": song["artist"],
            "title_album": title_album,
            "title": song["title"],
            "year": year,
            "album": song["album"],
            "img_url": image_name
        }

        print("Inserting item into DynamoDB")
        table.put_item(Item=item)
        print("Insert successful")

    except Exception as e:
        print("Error processing record:", str(e))
        raise

print("Processing completed successfully")