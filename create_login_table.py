
import boto3

# Connect to DynamoDB
dynamodb = boto3.resource('dynamodb')

# Table name
table_name = "login_v2"

print("Creating login table...")

# Create table
table = dynamodb.create_table(
    TableName=table_name,
    KeySchema=[
        {
            'AttributeName': 'email',
            'KeyType': 'HASH'   # Partition key
        }
    ],
    AttributeDefinitions=[
        {
            'AttributeName': 'email',
            'AttributeType': 'S'
        }
    ],
    BillingMode='PAY_PER_REQUEST'
)

# Wait until table is created
table.wait_until_exists()

print("Login table created successfully!")

# Insert 10 records
student_id = "s4163320"    
name = "DhiravShah"  

print("Inserting records...")

for i in range(10):
    email = f"{student_id}{i}@student.rmit.edu.au"
    username = f"{name}{i}"
    password = "".join([str((i + j) % 10) for j in range(6)])

    table.put_item(
        Item={
            "email": email,
            "user_name": username,
            "password": password
        }
    )

    print(f"Inserted: {email}")

print("All 10 records inserted successfully!")