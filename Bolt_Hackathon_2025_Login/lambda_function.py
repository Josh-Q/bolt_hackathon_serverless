import json
import boto3
import uuid
import time
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Initialize DynamoDB resource and table
dynamodb = boto3.resource('dynamodb')
usersTable = dynamodb.Table('Bolt_Hackathon_2025_Users')

headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Userid,Sessionid",
}
def lambda_handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        username = body.get('userName')
        password = body.get('password')

        if not username or not password:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "Missing username/password in request body"})
            }

        # Query using GSI
        query_params = {
            'IndexName': 'username-index',
            'KeyConditionExpression': Key('username').eq(username),
            'Limit': 1
        }

        response = usersTable.query(**query_params)
        items = response.get("Items", [])
        if not items:
            return {
                "statusCode": 404,
                "headers": headers,
                "body": json.dumps({"error": "User not found"})
            }

        item = items[0]

        if item.get("password") != password:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "Login failed"})
            }

        # Generate session
        session_id = str(uuid.uuid4())
        session_validity = int(time.time()) + 24 * 3600

        # Update session info in DB
        update_response = usersTable.update_item(
            Key={"UserId": item["UserId"]},
            UpdateExpression="SET currentActiveSessionId = :sid, sessionValidity = :validity",
            ExpressionAttributeValues={
                ":sid": session_id,
                ":validity": session_validity
            },
            ReturnValues="UPDATED_NEW"
        )

        filtered_user = {
            "UserId": item["UserId"],
            "sessionId": session_id
        }

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps(filtered_user)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)})
        }

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o % 1 == 0 else float(o)
        return super().default(o)
