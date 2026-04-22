import boto3

# Connect to DynamoDB
dynamodb = boto3.client('dynamodb')

table_name = "music_v2"

print("Creating music table...")

# Create table
dynamodb.create_table(
    TableName=table_name,
    KeySchema=[
        {'AttributeName': 'artist', 'KeyType': 'HASH'},
        {'AttributeName': 'title', 'KeyType': 'RANGE'}
    ],
    AttributeDefinitions=[
        {'AttributeName': 'artist', 'AttributeType': 'S'},
        {'AttributeName': 'title', 'AttributeType': 'S'},
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

# Wait until table exists
dynamodb.get_waiter('table_exists').wait(TableName=table_name)

print("Music table created successfully!")
