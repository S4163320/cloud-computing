"""
Creates music_v4 with base keys, one GSI, and one LSI.

LSIs cannot be added after table creation. If you need this schema on an
existing table name (e.g. music_v3), delete that table in the AWS console
(or CLI) first, then run this script — or use a new table name (music_v4).
"""

import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.client("dynamodb")

table_name = "music_v4"

print("Creating music table...")

try:
    dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {"AttributeName": "artist", "KeyType": "HASH"},
            {"AttributeName": "title_album", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "artist", "AttributeType": "S"},
            {"AttributeName": "title_album", "AttributeType": "S"},
            {"AttributeName": "album", "AttributeType": "S"},
            {"AttributeName": "year", "AttributeType": "S"},
        ],
        LocalSecondaryIndexes=[
            {
                "IndexName": "artist-year-index",
                "KeySchema": [
                    {"AttributeName": "artist", "KeyType": "HASH"},
                    {"AttributeName": "year", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "album-year-index",
                "KeySchema": [
                    {"AttributeName": "album", "KeyType": "HASH"},
                    {"AttributeName": "year", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    dynamodb.get_waiter("table_exists").wait(TableName=table_name)
    print("Music table created successfully!")

except ClientError as e:
    if e.response["Error"]["Code"] == "ResourceInUseException":
        print(
            "Table already exists. Delete it first if you need this schema "
            "(LSI cannot be added to an existing table)."
        )
    else:
        print("Error:", e)
