import json
import boto3
from decimal import Decimal
import json
from boto3.dynamodb.conditions import Key, Attr
 
# Initialize DynamoDB resource and table
dynamodb = boto3.resource('dynamodb')
userTable = dynamodb.Table('Bolt_Hackathon_2025_Users')
lambda_client = boto3.client('lambda') 
userBidsTable = dynamodb.Table('Bolt_Hackathon_2025_User_Bids')
sessionResultsTable = dynamodb.Table('Bolt_Hackathon_2025_Session_Results')
unqiue_models = ['Command Light','Jamba 1.5 Mini','Nova Lite']

headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Userid,Sessionid",
}
 


def lambda_handler(event, context):
    try:
        # Get query parameters (for GET requests)
        query_params = event.get('queryStringParameters') or {}

        userId = query_params.get('userId')
        
        if not userId:
            return {
                "statusCode": 400,
                "headers": headers,
                "body": json.dumps({"error": "Missing userId in request body"})
            }

        # Step 2: Query DynamoDB with the given userId
        response = userTable.get_item(
            Key={'UserId': userId}
        )

        item = response.get('Item')
        if not item:
            return {
                "statusCode": 404,
                "headers": headers,
                "body": json.dumps({"error": "User not found"})
            }


        payload = {
            "method": "balance",
            "body": json.dumps({
                "address": item.get("key") 
            })
        }

        crypto_response = lambda_client.invoke(
            FunctionName='Bolt_Hackathon_2025_BlockChain_Common_Service',
            InvocationType='RequestResponse',  
            Payload=json.dumps(payload)
        )

        raw_payload = crypto_response['Payload'].read()
        decoded_payload = json.loads(raw_payload)


        body_str = decoded_payload.get("body")  # Still a string

        # Step 2: Parse the inner JSON string
        body_dict = json.loads(body_str)

        # Step 3: Now extract balance
        balance = body_dict.get("balance")

        response = userBidsTable.query(
            IndexName='userId-index',  # 🔁 Replace with your GSI name
            KeyConditionExpression=Key('userId').eq(userId)
        )

        loseCount = 0
        winCount = 0

        totalEarning = 0
        totalBets= 0 
        print(response['Items'])
        for bids in response['Items']:
            totalBets += 1
            if bids['sessionStatus'] == 'LOSE':
                totalEarning -= bids['bidAmount']
                loseCount += 1
            elif bids['sessionStatus'] == 'WIN':
                winCount += 1
                totalEarning -= bids['bidAmount']
                totalEarning += bids['payoutAmount']


        total = winCount + loseCount

        if total == 0:
            winRate = 0.0
        else:
            winRate = (winCount / total) * 100

        modelWinRates = []

        for model in unqiue_models:
            modelWinRates.append({
                'modelName': model,
                'winRate': getAverageAccuracy(model) * 100
            })

        filtered_user = {
            "userId": item.get("UserId"),
            "username": item.get("username"),
            "balance": balance,
            "winRate": winRate,
            "totalBets": totalBets,
            "totalEarning": totalEarning,
            "modelWinRates": modelWinRates
        }

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"user": filtered_user}, cls=DecimalEncoder)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)})
        }


def getAverageAccuracy(model_name):
    # Query GSI (assuming it's named 'model_name-timestamp-index')
    
    response = sessionResultsTable.query(
        IndexName='modelName-candleTimestamp-index',  # Replace with your actual GSI name
        KeyConditionExpression=Key('modelName').eq(model_name),
        FilterExpression=Attr('accuracy').exists(),
        ScanIndexForward=False,  # descending order
        Limit=10
    )
    items = response.get('Items', [])
    
    # print(f"Items for model {model_name}: {items}")

    win_count = sum(1 for item in items if item.get('sessionStatus') == 'WIN')
    lose_count = sum(1 for item in items if item.get('sessionStatus') == 'LOSE')
    total = win_count + lose_count

    # print(model_name)
    # print(win_count)
    # print(lose_count)

    if total == 0:
        avg_accuracy = 0  # or Decimal('0') if you're using Decimals
    else:
        avg_accuracy = win_count / total

    return avg_accuracy

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, Decimal):
            # Choose int or float depending on your needs
            return int(o) if o % 1 == 0 else float(o)
        return super(DecimalEncoder, self).default(o)
 
 