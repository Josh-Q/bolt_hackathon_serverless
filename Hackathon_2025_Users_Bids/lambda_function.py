import json
import boto3
from decimal import Decimal
from boto3.dynamodb.conditions import Key

# Initialize DynamoDB resource and table
dynamodb = boto3.resource('dynamodb')
userTable = dynamodb.Table('Bolt_Hackathon_2025_User_Bids')

headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "*",
}


class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return int(o) if o % 1 == 0 else float(o)
        return super(DecimalEncoder, self).default(o)


def lambda_handler(event, context):
    try:
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        userId = body.get('userId')
        roundId = body.get('roundId')
        lastEvaluatedKey = body.get('lastEvaluatedKey')

        if not userId:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "Missing userId in request body"})
            }

        # ✅ CASE 1: Specific roundId provided - get single bid
        if roundId:
            response = userTable.get_item(
                Key={
                    'userId': userId,
                    'roundId': roundId
                }
            )
            item = response.get('Item')
            if not item:
                return {
                    "statusCode": 404,
                    "headers": headers,
                    "body": json.dumps({"error": "Bid not found"})
                }

            filtered_bid = {
                "roundId": item.get("roundId"),
                "bidAmount": item.get("bidAmount"),
                # "isClosed": item.get("isClosed"),
                # "isWinning": item.get("isWinning"),
                "payoutAmount": item.get("payoutAmount"),
                "prediction": item.get("prediction"),
            }

            return {
                "statusCode": 200,
                "headers": headers,
                "body": json.dumps({"userBid": filtered_bid}, cls=DecimalEncoder)
            }

        # ✅ CASE 2: No roundId - paginate all user bids
        query_params = {
            'IndexName': 'userId-index',
            'KeyConditionExpression': Key('userId').eq(userId),
            'Limit': 10,
            'ScanIndexForward': False
        }

        if lastEvaluatedKey:
            query_params['ExclusiveStartKey'] = lastEvaluatedKey

        response = userTable.query(**query_params)
 
        items = response.get('Items', [])
        filtered_items = [
            {
                "roundId": i.get("roundId"),
                "bidAmount": i.get("bidAmount"),
                # "isClosed": i.get("isClosed"),
                # "isWinning": i.get("isWinning"),
                "payoutAmount": i.get("payoutAmount"),
                "prediction": i.get("prediction"),
            }
            for i in items
        ]

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({
                "userBids": filtered_items,
                "lastEvaluatedKey": response.get("LastEvaluatedKey")  # for client-side pagination
            }, cls=DecimalEncoder)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)})
        }



# {
#   "body": "{\"userId\": \"user-123\", \"roundId\": \"session-001\"}"
# }

# {
#   "body": "{\"userId\": \"user-123\"}"
# }

# {
#   "body": "{\"userId\": \"user-123\", \"lastEvaluatedKey\": {\"UserId\": \"user-123\", \"roundId\": \"session-001\"}}"
# }
