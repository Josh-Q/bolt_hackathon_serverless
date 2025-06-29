import boto3
import os
import time

dynamodb = boto3.resource('dynamodb')
usersTable = dynamodb.Table('Bolt_Hackathon_2025_Users')
method_arn = "arn:aws:execute-api:ap-southeast-1:123456789012:jspb038js0/bolt/*/*"

# headers = {
#     "Access-Control-Allow-Origin": "*",
#     "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
#     "Access-Control-Allow-Headers": "*",
# }



def lambda_handler(event, context):
    user_id = event.get("headers", {}).get("userid")
    session_id = event.get("headers", {}).get("sessionid")


    if not user_id:
        # return {
        #     "statusCode": 500,
        #     "headers": headers,
        #     "body": json.dumps({"error": "Missing userId"})
        # }
        raise Exception("Unauthorized")


    try: 
        response = usersTable.get_item(Key={"UserId": user_id})
        item = response.get("Item")

        if not item:
            # return {
            #     "statusCode": 500,
            #     "headers": headers,
            #     "body": json.dumps({"error": "User not found"})
            # }
            raise Exception("Unauthorized")

        stored_session_id = item.get("currentActiveSessionId")
        session_validity = item.get("sessionValidity")
        
        current_time = int(time.time())

        if session_id != stored_session_id or session_validity < current_time:
            # return {
            #     "statusCode": 500,
            #     "headers": headers,
            #     "body": json.dumps({"error": "Invalid session"})
            # }
            raise Exception("Unauthorized")

        # return allow_all
        return generate_policy(user_id, "Allow", event["methodArn"])

    except Exception as e:
        print(f"Auth error: {str(e)}")
        # return {
        #     "statusCode": 500,
        #     "headers": headers,
        #     "body": json.dumps({"error": str(e)})
        # }
        raise Exception("Unauthorized")

def is_login_path(event):
    """Check if the path is /login"""
    method_arn = event["methodArn"]  # e.g. arn:aws:execute-api:<region>:<acct>:<apiId>/<stage>/<verb>/<resource>
    try:
        parts = method_arn.split('/')
        resource_path = '/'.join(parts[3:])  # gets everything after stage
        return resource_path.endswith("/login") or resource_path == "login"
    except Exception:
        return False

def allow_all(principal_id, method_arn):
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": method_arn
                }
            ]
        }
    }


def generate_policy(principal_id, effect, resource):
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": effect,
                    "Resource": resource
                }
            ]
        },
        "context": {
            "userId": principal_id,
        }
    }