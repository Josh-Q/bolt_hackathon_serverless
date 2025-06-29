import json
import boto3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from boto3.dynamodb.conditions import Key
  
dynamodb = boto3.resource('dynamodb')
userBidsTable = dynamodb.Table('Bolt_Hackathon_2025_User_Bids')
userTable = dynamodb.Table('Bolt_Hackathon_2025_Users')
sessionTable = dynamodb.Table('Bolt_Hackathon_2025_Sessions')
lambda_client = boto3.client('lambda') 

headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "*",
}


 
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


def insertBid(item):
        # Put item in DynamoDB
    userBidsTable.put_item(Item=item)

    # Return success with created bid info
    return {
        "statusCode": 200,
        "headers": headers,
        "body": json.dumps({"message": "Bid created successfully"}, cls=DecimalEncoder)
    }

def lambda_handler(event, context):
    try:
        user_id = event['requestContext']['authorizer']['userId']
        # Parse request body
        body = json.loads(event.get('body', '{}'))
        round_id, bid_amount , prediction = validateInputs(body)

        user = validateUser(user_id)
        
        item = prepareBid(user_id, round_id, bid_amount , prediction)

        validateBalanceOnBlockChain(user,bid_amount)

        return insertBid(item)
        

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)})
        }


def validateBalanceOnBlockChain(user,bid_amount):

    payload = {
            "method": "send_to_house",
            "body": json.dumps({
                "fromMnemonic": user.get("mnemonic"),
                "amount": bid_amount 
            })
        } 

    crypto_response = lambda_client.invoke(
        FunctionName='Bolt_Hackathon_2025_BlockChain_Common_Service',
        InvocationType='RequestResponse',  
        Payload=json.dumps(payload)
    )
    response_payload = crypto_response['Payload'].read()
    response_json = json.loads(response_payload)

    status_code = response_json.get("statusCode")
    body = json.loads(response_json.get("body"))

    if status_code != 200:
        raise Exception(f"Blockchain balance check failed: {body.get('error', 'Unknown error')}")


def prepareBid(user_id, round_id, bid_amount , prediction):

    # response = sessionTable.query(
    #     KeyConditionExpression=Key('roundId').eq(round_id)
    # )
    response = sessionTable.query(
        IndexName='roundId-index',  # ✅ Name of your GSI
        KeyConditionExpression=Key('roundId').eq(round_id),
        Limit=1
    )

    items = response.get('Items', [])
    bid = items[0] if items else None
    now = datetime.now(timezone.utc)
    if not bid: 
        raise Exception(f"Session is not found.")

    response = userBidsTable.query(KeyConditionExpression=Key('userId').eq(user_id) & Key('roundId').eq(round_id))

    if response.get('Items'):
        raise Exception(f"Already have an active bid for this session.")

        # Parse the stored time from bid
    start_time_str = bid.get('candleTimestamp')  # or whatever the field is
    start_time = datetime.fromisoformat(start_time_str) if start_time_str else None

    if (start_time and start_time < now):
        raise Exception(f"Session has ended.")

    # Prepare item to put in DynamoDB
    return {
        'roundId': round_id,
        'userId': user_id,
        'bidAmount': Decimal(str(bid_amount)),
        'createdAt': datetime.utcnow().isoformat(),
        'prediction': prediction,
        'sessionStatus': 'OPEN',
        'payoutAmount': 0
    }


def validateInputs(body):
    round_id = body.get('roundId')
    bid_amount = body.get('bidAmount')
    prediction = body.get('prediction')

    # Validate input
    if not round_id or bid_amount is None or prediction is None:
        return {
            "statusCode": 400,
            "headers": headers,
            "body": json.dumps({"error": "Missing required fields: roundId, bidAmount, prediction"})
        }
    return round_id, bid_amount, prediction

def validateUser(user_id):
    userObject = userTable.query(
        KeyConditionExpression=Key('UserId').eq(user_id)
    )

    # Check if user exists
    if not userObject.get('Items'):
        return {
            "statusCode": 404,
            "headers": headers,
            "body": json.dumps({"error": f"User '{user_id}' not found"})
        }

    # Optionally get the user data if needed
    return userObject['Items'][0]

        