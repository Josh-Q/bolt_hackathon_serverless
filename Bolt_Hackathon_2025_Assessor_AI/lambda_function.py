import boto3
import json
from datetime import datetime
from boto3.dynamodb.conditions import Key, Attr
from decimal import Decimal, InvalidOperation
import uuid

lambda_client = boto3.client('lambda') 
dynamodb = boto3.resource('dynamodb')
sessionResultsTable = dynamodb.Table('Bolt_Hackathon_2025_Session_Results')
sessionsTable = dynamodb.Table('Bolt_Hackathon_2025_Sessions')
userTable = dynamodb.Table('Bolt_Hackathon_2025_Users')
userBidsTable = dynamodb.Table('Bolt_Hackathon_2025_User_Bids')

payout_threshold = Decimal('0.998')

 
def lambda_handler(event, context):

    mock = False
    round_id = str(uuid.uuid4())

    if mock:
         answers, prediction_candle_timestamp, previous_close_price, actualData = generateMockData()
    else:
        answers, prediction_candle_timestamp, previous_close_price, actualData = invoke_prediction_lambda()

    objects_to_store = []

    uniqueModals = []

    # Format output nicely
    for model, prediction in answers.items():
        average_accuracy = getAverageAccuracy(model)

        payout_ratio = calculate_payout(average_accuracy)

        objects_to_store.append(build_objects_to_store(model, prediction.strip('.'), prediction_candle_timestamp,previous_close_price,payout_ratio,round_id))
        uniqueModals.append(model)

    storeSessionObject(prediction_candle_timestamp,uniqueModals,round_id)

    uniqueModals = set(uniqueModals)
    store_prediction(objects_to_store)

    winners = update_actual_value(actualData["candles"], uniqueModals)

    update_user_bids_table(winners)

    return {
        'statusCode': 200,
        'body': json.dumps({
            "message": "Called second lambda",
            "savedData": objects_to_store
        }, default=str)
    }



def update_user_bids_table(winners):
        # Now handle DB update for those winners
    winning_bids = []

    for winner in winners:
        round_id = winner['roundId']
        model_name = winner['modelName']
        payoutRatio = winner['payoutRatio']

        response = userBidsTable.query(
            IndexName='roundId-userId-index',
            KeyConditionExpression=Key('roundId').eq(round_id)
            # FilterExpression=Attr('sessionStatus').eq('OPEN')
        )

        items = response.get('Items', [])

        for item in items:
            user_ids = [bid['userId'] for bid in winning_bids if 'userId' in bid and bid['userId']]
            if item['userId'] in user_ids:
                continue
 
            new_status = "WIN" if item['prediction'] == model_name else "LOSE"           

            userBidsTable.update_item(
                Key={
                    'roundId': item['roundId'], 
                    'userId': item['userId']
                },
                UpdateExpression="SET sessionStatus = :new_status, payoutAmount = :pay_out",
                ExpressionAttributeValues={
                    ':new_status': new_status,  # e.g., 'WIN' or 'LOSE'
                    ':pay_out': Decimal(item['bidAmount']) * payoutRatio
                }
            )

            if new_status == "WIN":
                winning_bids.append({
                    'userId': item['userId'],
                    'payoutAmount': Decimal(item['bidAmount']) * payoutRatio,                    
                })

    payout_users(winning_bids)


def payout_users(winning_bids):
    print(winning_bids)
    user_ids = [bid['userId'] for bid in winning_bids if 'userId' in bid and bid['userId']]
    keys = [{'UserId': uid} for uid in user_ids]

    if not keys:
        return

    response = dynamodb.batch_get_item(
        RequestItems={
            'Bolt_Hackathon_2025_Users': {
                'Keys': keys
            }
        }
    ) 
    users = response['Responses']['Bolt_Hackathon_2025_Users']

    for user in users:
        user_id = user['UserId']        
        for winning_bid in winning_bids:
            if winning_bid['userId'] == user_id:
                print("sending to user : ", user_id)
                payload = {
                    "method": "send_to_user",
                    "body": json.dumps({
                        "toAddress": user['key'],
                        "amount": float(winning_bid['payoutAmount'])
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



def invoke_prediction_lambda():
    # Prepare payload to send to the second lambda
    payload = {
        "key1": "value1",
        "key2": "value2"
    }
    
    response = lambda_client.invoke(
        FunctionName='Bolt_Hackathon_2025',  # replace with your second lambda name or ARN
        InvocationType='RequestResponse',  # 'Event' for async, 'RequestResponse' for sync
        Payload=json.dumps(payload)
    )
    # Read the response if synchronous
    response_payload = response['Payload'].read().decode('utf-8')

    response_data = json.loads(response_payload)
    
    # Parse the outer body (string inside 'body' field)
    outer_body = json.loads(response_data["body"])

     # Extract the answers dictionary 
    answers = outer_body.get("Answers", {})

    # Extract the prediction candle timestamp
    prediction_candle_timestamp = outer_body.get("PredictionCandleTimestamp", {})
   
    # Extract the previous close price
    previous_close_price = outer_body.get("PreviousClose", {})

    # Extract the actual past candle data
    actualData = outer_body.get("ActualData", {})
    return answers, prediction_candle_timestamp, previous_close_price, json.loads(actualData)


def build_objects_to_store(model_name, prediction,prediction_candle_timestamp,previous_close_price,payout_ratio,round_id):
    item = {        
        'roundId': round_id, # unique identifier
        'candleTimestamp': prediction_candle_timestamp, # timestamp of candle to be predicted
        'modelName': model_name, # name of AI model
        'previousClose': previous_close_price, # previous close price
        'prediction': prediction, #  value
        'actualClose': None, # actual closing price of candle
        'accuracy': None, # was the prediction accurate
        'createdAt': datetime.utcnow().isoformat(), # unique identifier 
        'updatedAt': None,
        'payoutRatio': Decimal(payout_ratio),
        'sessionStatus': None
    }
    return item

def store_prediction(items_to_store):
    with sessionResultsTable.batch_writer() as batch:
        for item in items_to_store:
            batch.put_item(Item=item)

def update_actual_value(actualData, uniqueModals):
    if not actualData:
        print("No data provided.")
        return

    # Step 1: Normalize and validate entries
    valid_actual_data = [
        entry for entry in actualData
        if isinstance(entry, dict) and 'timestamp' in entry and 'close' in entry
    ]

    if not valid_actual_data:
        print("No valid entries found.")
        return

    # Step 2: Build lookup for candles by timestamp
    actual_data_candle_map = {entry['timestamp']: entry for entry in valid_actual_data}

    # Step 4: Prepare composite keys for batch_get_item
    keys = [
        {
            'candleTimestamp': timestamp,
            'modelName': model_name
        }
        for timestamp in actual_data_candle_map
        for model_name in uniqueModals
    ]

    # Step 5: Batch get in chunks of 100
    chunks = [keys[i:i + 100] for i in range(0, len(keys), 100)]
    items_to_update = []

    for chunk in chunks:
        # print("chunk:", chunk)
        response = sessionResultsTable.meta.client.batch_get_item(
            RequestItems={
                sessionResultsTable.name: {
                    'Keys': chunk
                }
            }
        )
        returned_items = response['Responses'].get(sessionResultsTable.name, [])
        # print("returned items:", returned_items)

        for item in returned_items:
            if item.get('accuracy') is None:
                items_to_update.append(item)
    
    winners = []
    # Step 6: Update only items missing "accuracy"
    for item in items_to_update:
        ts = item['candleTimestamp']
        model_name = item['modelName']
        updated_round_id = item['roundId']
        payoutRatio = item['payoutRatio']
        candle = actual_data_candle_map.get(ts)

        # print(ts, model_name, candle)

        if candle and 'close' in candle:
            try:
                close_price = Decimal(candle['close'])
                # previous_close = Decimal(item['previousClose'])    
                prediction = Decimal(item['prediction'])    
                if close_price == 0:
                    accuracy = None
                else:
                    accuracy = 1 - (abs(close_price - prediction) / close_price)
            except (InvalidOperation, TypeError, ValueError):
                accuracy = None
            updatedAt = datetime.utcnow().isoformat()
            actualClose = candle['close']

            sessionStatus = "WIN" if accuracy is not None and accuracy > payout_threshold else "LOSE"
            
            sessionResultsTable.update_item(
                Key={
                    'candleTimestamp': ts,
                    'modelName': model_name
                },
                UpdateExpression='SET accuracy = :accuracy, updatedAt = :updatedAt, actualClose = :actualClose, sessionStatus = :sessionStatus',
                ExpressionAttributeValues={
                    ':accuracy': accuracy,
                    ':updatedAt': updatedAt,
                    ':actualClose': actualClose,
                    ':sessionStatus': sessionStatus
                }
            )
            if accuracy is not None and accuracy > payout_threshold:
                winners.append({
                    'roundId': updated_round_id,
                    'modelName': model_name,
                    'payoutRatio': payoutRatio
                })

        if not winners:
            winners.append({
                'roundId': updated_round_id,
                'modelName': '',
                'payoutRatio': 0
            })

    return winners

def storeSessionObject(prediction_candle_timestamp,models,round_id):
    item = {
        'roundId': round_id,
        'candleTimestamp':prediction_candle_timestamp ,
        'createdAt': datetime.utcnow().isoformat(),
        # 'models': models,
        'type': 'round'
        # 'updatedAt': None
    }
    sessionsTable.put_item(Item=item)

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

    win_count = sum(1 for item in items if item.get('sessionStatus') == 'WIN')
    lose_count = sum(1 for item in items if item.get('sessionStatus') == 'LOSE')
    avg_accuracy = win_count / (lose_count + win_count)

    return avg_accuracy


def calculate_payout(avg_accuracy):
    
    max_payout = Decimal('5')

    avg_accuracy = Decimal(str(avg_accuracy))
    # if avg_accuracy >= Decimal('1'):
    #     return Decimal('0')
    # if avg_accuracy >= payout_threshold:
    #     return Decimal('1.01')
    # payout = (payout_threshold - avg_accuracy) / (1 - avg_accuracy)
    payout = 1 / avg_accuracy

    return min(payout + Decimal('0.01'), max_payout)

def generateMockData():
    answers = {'Jamba 1.5 Mini': '104468.57000000'}
    prediction_candle_timestamp = '2025-06-18T10:33:00Z'
    previous_close_price = '104468.57000000'
    actualData = {
    "candles": [
    {
    "timestamp": "2025-06-18T10:23:00Z",
    "open": "104505.45000000",
    "high": "104570.11000000",
    "low": "104487.17000000",
    "close": "104542.80000000",
    "volume": "32.46379000"
    },
    {
    "timestamp": "2025-06-18T10:24:00Z",
    "open": "104542.79000000",
    "high": "104562.14000000",
    "low": "104521.72000000",
    "close": "104558.22000000",
    "volume": "5.48886000"
    },
    {
    "timestamp": "2025-06-18T10:25:00Z",
    "open": "104558.22000000",
    "high": "104558.23000000",
    "low": "104530.27000000",
    "close": "104540.85000000",
    "volume": "3.68330000"
    },
    {
    "timestamp": "2025-06-18T10:26:00Z",
    "open": "104540.85000000",
    "high": "104540.85000000",
    "low": "104521.50000000",
    "close": "104521.51000000",
    "volume": "2.66759000"
    },
    {
    "timestamp": "2025-06-18T10:27:00Z",
    "open": "104521.51000000",
    "high": "104543.57000000",
    "low": "104499.01000000",
    "close": "104508.85000000",
    "volume": "14.22921000"
    },
    {
    "timestamp": "2025-06-18T10:28:00Z",
    "open": "104508.86000000",
    "high": "104508.86000000",
    "low": "104497.05000000",
    "close": "104497.06000000",
    "volume": "2.93984000"
    },
    {
    "timestamp": "2025-06-18T10:29:00Z",
    "open": "104497.06000000",
    "high": "104508.85000000",
    "low": "104497.06000000",
    "close": "104500.81000000",
    "volume": "2.04941000"
    },
    {
    "timestamp": "2025-06-18T10:30:00Z",
    "open": "104500.81000000",
    "high": "104543.49000000",
    "low": "104500.80000000",
    "close": "104543.48000000",
    "volume": "6.44607000"
    },
    {
    "timestamp": "2025-06-18T10:31:00Z",
    "open": "104543.49000000",
    "high": "104543.61000000",
    "low": "104490.20000000",
    "close": "104543.61000000",
    "volume": "7.52716000"
    },
    {
    "timestamp": "2025-06-18T10:32:00Z",
    "open": "104543.61000000",
    "high": "104543.61000000",
    "low": "104543.61000000",
    "close": "104543.61000000",
    "volume": "0.04483000"
    }
    ]
    }
    return answers, prediction_candle_timestamp, previous_close_price, actualData  