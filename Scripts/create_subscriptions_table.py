import boto3

dynamodb = boto3.resource("dynamodb")
table_name = "subscriptions_v1"

print("Creating subscriptions table...")

table = dynamodb.create_table(
    TableName=table_name,
    KeySchema=[
        {"AttributeName": "email", "KeyType": "HASH"},
        {"AttributeName": "song_id", "KeyType": "RANGE"},
    ],
    AttributeDefinitions=[
        {"AttributeName": "email", "AttributeType": "S"},
        {"AttributeName": "song_id", "AttributeType": "S"},
    ],
    BillingMode="PAY_PER_REQUEST"
)

table.wait_until_exists()
print("Subscriptions table created successfully!")