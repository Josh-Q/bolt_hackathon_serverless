import json
import boto3
import requests
import datetime

# Bedrock and Bedrock Runtime clients
bedrock = boto3.client("bedrock", region_name="us-east-1")
bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")
predictionCandleTimestamp = None
previousClose = None


def lambda_handler(event, context):
    global predictionCandleTimestamp , previousClose
    try:
        
        # Get model list
        foundation_models = bedrock.list_foundation_models(byInferenceType="ON_DEMAND")
        # model_names = [model["modelName"] for model in foundation_models["modelSummaries"]]
        # model_names = [
        #     model["modelName"]
        #     for model in foundation_models["modelSummaries"]
        #     if "TEXT" in model.get("outputModalities", [])
        # ]
        # print(model_names)
        # return
        actualData = get_crypto_data()
        prompt = parse_prompt(actualData)

        if prompt is None:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Missing 'input.question' in request"})
            }
        
        answer1 = get_model(foundation_models,"Jamba 1.5 Mini",prompt)
        answer2 = get_model(foundation_models,"Nova Lite",prompt)
        answer3 = get_model(foundation_models,"Command Light",prompt)
        # answer4 = get_model(foundation_models,"Llama 3 8B Instruct",prompt)
        # answer5 = get_model(foundation_models,"Mistral 7B Instruct",prompt)
        # # answer6 = get_model(foundation_models,"SDXL 1.0",prompt)
        # answer7 = get_model(foundation_models, "Titan Text G1 - Express", prompt)
        # # answer8 = get_model(foundation_models, "Claude Instant", prompt)

        return {
            "statusCode": 200,
            "headers": {
                "Access-Control-Allow-Headers": "*",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "OPTIONS,POST,GET"
            },
            "body": json.dumps({
                "ActualData": actualData,
                "PreviousClose": previousClose,
                "PredictionCandleTimestamp": predictionCandleTimestamp.isoformat() + "Z",
                "Answers": {
                    "Jamba 1.5 Mini": answer1.strip(),
                    "Nova Lite": answer2.strip(),
                    "Command Light": answer3.strip(),
                    # "Llama 3 8B Instruct": answer4.strip(),
                    # "Mistral 7B Instruct": answer5.strip(),
                    # # "SDXL 1.0": answer6.strip()
                    # "Titan Text G1 - Express": answer7.strip()
                    # # "Claude Instant": answer8.strip()
                }
            })
        }

    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }

def call_bedrock(prompt,matching_model):
    # Construct payload
    payload = build_payload(matching_model["modelId"], prompt)
    # Call Bedrock
    
    modelId = sanitize_model_id(matching_model)
    
    response = bedrock_runtime.invoke_model(
        body=json.dumps(payload),
        modelId=modelId,
        accept="application/json",
        contentType="application/json")
 
    

    response_body = json.loads(response.get('body').read())
    answer = build_response(modelId,response_body)
    # answer = response_body["choices"][0]["message"]["content"]

    return answer

def parse_prompt(body_json):
    # Parse prompt    
    prompt = (
    "Given the following candlestick data (timestamp, open, high, low, close, volume) for the last 10 candles:\n"
    + json.dumps(body_json, indent=2)
    + "\nPredict the next candle's *closing price*. "
    + "Respond with only a single number, no words, no symbols, no explanation."
    )
    # print("INPUT PROMPT : ", prompt) 
    return prompt

def get_model(foundation_models,modelName,prompt):
    # Look for the Jamba 1.5 Mini model
    matching_model = next(
        (model for model in foundation_models["modelSummaries"] 
            if model.get("modelName") == modelName), None
    )

    if not matching_model:
        return "Model : " + modelName + " not found"

    return call_bedrock(prompt,matching_model)

def sanitize_model_id(matching_model):
    # if matching_model["providerName"] == "Amazon":
    #     print("model ID : ", matching_model["modelId"].split(":")[0])
    #     return matching_model["modelId"].split(":")[0]
    # print("model ID : ", matching_model["modelId"])
    return matching_model["modelId"]

def build_payload(model_id, prompt):
    max_tokens = 10
    temperature = 0.7
    
    if model_id.startswith("anthropic."):
        return {
            "prompt": prompt,
            "max_tokens_to_sample": max_tokens,
            "temperature": temperature,
            "top_p": 1
        }
    elif model_id.startswith("ai21."):
        return {
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }
    elif model_id.startswith("amazon.nova"):
        inf_params = {"maxTokens": max_tokens, "topP": 1, "topK": 1, "temperature": temperature}
        return {
            "inferenceConfig": inf_params,
            "messages": [
                { "role": "user",
                "content": [
                    {
                    "text": prompt
                    }
                ]
                }
            ]
        }
    elif model_id.startswith("amazon.titan"):
        return {
            "inputText": prompt,
            "textGenerationConfig": {
                "temperature": temperature,  
                "topP": 1,
                "maxTokenCount": max_tokens
            }
        }
    elif model_id.startswith("meta."):
        return {
            "prompt": prompt,
            "temperature": temperature,
            "max_gen_len": max_tokens
        }
    elif model_id.startswith("mistral."):
        return {
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    elif model_id.startswith("cohere."):
        return {
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
    else:
        raise Exception(f"Unsupported model input type for: {model_id}")

def build_response(model_id,payload):
    
    if model_id.startswith("anthropic."):
        return ""
    elif model_id.startswith("ai21."):
        return payload["choices"][0]["message"]["content"]
    elif model_id.startswith("amazon.nova"):
        return payload["output"]["message"]["content"][0]["text"]
    elif model_id.startswith("amazon.titan"):
        return payload["results"][0]["outputText"]
    elif model_id.startswith("meta."):
        return payload["generation"]
    elif model_id.startswith("mistral."):
        return payload["outputs"][0]["text"]
    elif model_id.startswith("cohere."):
        return payload["generations"][0]["text"]
    else:
        raise Exception(f"Unsupported model output type for: {model_id}")

def get_crypto_data():
    global predictionCandleTimestamp, previousClose
    interval = 5
    url = "https://api.binance.com/api/v3/klines"
    params = {
        "symbol": "DOGEUSDT",
        "interval": str(interval) + "m",
        "limit": 20
    }

    response = requests.get(url, params=params)
    data = response.json()

    candles = []

    data.sort(key=lambda candle: candle[0])


    for candle in data:
        open_time_ms = candle[0]
        dt = datetime.datetime.utcfromtimestamp(open_time_ms / 1000)
        candle_dict = {
            "timestamp": dt.isoformat() + "Z",  # ISO 8601 in UTC
            "open": candle[1],
            "high": candle[2],
            "low": candle[3],
            "close": candle[4],
            "volume": candle[5],
        }
        candles.append(candle_dict)
    

    # Get last candle's timestamp string
    last_timestamp_str = candles[-1]["timestamp"]  

    # Parse to datetime (strip trailing 'Z' for parsing)
    last_timestamp = datetime.datetime.strptime(last_timestamp_str.rstrip("Z"), "%Y-%m-%dT%H:%M:%S")

    # Add 1 minute
    predictionCandleTimestamp = last_timestamp + datetime.timedelta(minutes=interval)

    previousClose = candles[-1]["close"] 

    # Convert back to ISO 8601 string with Z
    predictionCandleTimestamp_str = predictionCandleTimestamp.isoformat() + "Z"

    output = {"candles": candles}

    return json.dumps(output, indent=2)
