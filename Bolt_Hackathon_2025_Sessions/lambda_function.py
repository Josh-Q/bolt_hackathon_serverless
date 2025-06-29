import json
import datetime
import boto3
from boto3.dynamodb.conditions import Key, Attr
 
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('Bolt_Hackathon_2025_Sessions')
results_table = dynamodb.Table('Bolt_Hackathon_2025_Session_Results')

 
headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "*",
}


def lambda_handler(event, context):
    try:

        # Get query parameters (for GET requests)
        query_params = event.get('queryStringParameters') or {}

        limit = int(query_params.get('limit', 50))
        # is_past = str_to_bool(query_params.get('isPast', False))

        # # Parse JSON body (POST)
        # body = json.loads(event.get('body') or '{}')
        
        # limit = int(body.get('limit', 50))
        # is_past = str_to_bool(body.get('isPast', False))

        now = datetime.datetime.utcnow()
        now_str = now.strftime('%Y-%m-%dT%H:%M:%S')

        # if is_past:
        #     condition = Key('type').eq('round') & Key('candleTimestamp').lt(now_str)
        #     scan_forward = False
        # else:
        #     condition = Key('type').eq('round') & Key('candleTimestamp').gt(now_str)
        #     scan_forward = True

        condition = Key('type').eq('round') 
        scan_forward = False

        response = table.query(
            IndexName='type-candleTimestamp-index',        # <-- Add this line to query the GSI
            KeyConditionExpression=condition,
            ScanIndexForward=scan_forward,
            Limit=limit
        )

        sessions = response.get('Items', [])

        output = []
        round_ids = [session['roundId'] for session in sessions if 'roundId' in session]

        # Batch query results by roundId (use query if roundId is partition key)
        results_by_round = {}
 
        for rid in round_ids:
            result_resp = results_table.query(
                IndexName='roundId-index',  # 🔁 Use your actual GSI name here
                KeyConditionExpression=Key('roundId').eq(rid),
            )
            round_models = result_resp.get('Items', [])
            results_by_round[rid] = round_models

        # Build response
        for session in sessions:
            candle_str = session.get('candleTimestamp')
            candle_str_with_z = candle_str
            try:
                candle_time = datetime.datetime.strptime(candle_str.rstrip("Z"), '%Y-%m-%dT%H:%M:%S')
            except: 
                status = 'unknown'
            else:
                delta = (candle_time - now).total_seconds()
                if delta < 0:
                    status = 'past'
                elif delta <= 60:
                    status = 'ongoing'
                else:
                    status = 'scheduled'

            round_id = session.get('roundId')
            output.append({
                'roundId': round_id,
                # 'modelName': session.get('modelName'),
                'candleTimestamp': candle_str_with_z,
                'statusLabel': status,
                'models': results_by_round.get(round_id, [])  # list of winners, could be empty
            })

        return {
            "statusCode": 200,
            "headers": headers,
            "body": json.dumps({"sessions": output}, default=str)
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "headers": headers,
            "body": json.dumps({"error": str(e)})
        }
 

def str_to_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == 'true'
    return False
