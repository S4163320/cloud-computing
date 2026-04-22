
import boto3
from botocore.exceptions import ClientError

dynamodb = boto3.client('dynamodb')

table_name = "music_v3"

print("Creating music table...")

try:
    dynamodb.create_table(
        TableName=table_name,
        KeySchema=[
            {'AttributeName': 'artist', 'KeyType': 'HASH'},
            {'AttributeName': 'title_album', 'KeyType': 'RANGE'}
        ],
        AttributeDefinitions=[
            {'AttributeName': 'artist', 'AttributeType': 'S'},
            {'AttributeName': 'title_album', 'AttributeType': 'S'},
            {'AttributeName': 'album', 'AttributeType': 'S'},
            {'AttributeName': 'year', 'AttributeType': 'S'}
        ],
        GlobalSecondaryIndexes=[
            {
                'IndexName': 'album-year-index',
                'KeySchema': [
                    {'AttributeName': 'album', 'KeyType': 'HASH'},
                    {'AttributeName': 'year', 'KeyType': 'RANGE'}
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
            }
        ],
        BillingMode='PAY_PER_REQUEST'
    )

    dynamodb.get_waiter('table_exists').wait(TableName=table_name)
    print("Music table created successfully!")

except ClientError as e:
    if e.response['Error']['Code'] == 'ResourceInUseException':
        print("Table already exists. Please delete it first or use another table name.")
    else:
        print("Error:", e)