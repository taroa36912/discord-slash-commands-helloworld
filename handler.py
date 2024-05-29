import json, os, requests
from nacl.signing import VerifyKey
from concurrent.futures import ThreadPoolExecutor

DISCORD_ENDPOINT = "https://discord.com/api/v8"

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
APPLICATION_ID = os.getenv('APPLICATION_ID')
APPLICATION_PUBLIC_KEY = os.getenv('APPLICATION_PUBLIC_KEY')
COMMAND_GUILD_ID = os.getenv('COMMAND_GUILD_ID')

verify_key = VerifyKey(bytes.fromhex(APPLICATION_PUBLIC_KEY))

executor = ThreadPoolExecutor(max_workers=5)

def registerCommands():
    endpoint = f"{DISCORD_ENDPOINT}/applications/{APPLICATION_ID}/guilds/{COMMAND_GUILD_ID}/commands"
    print(f"registering commands: {endpoint}")

    commands = [
        {
            "name": "ynu",
            "description": "Input what you want to know!",
            "options": [
                {
                    "type": 3, # ApplicationCommandOptionType.String
                    "name": "message",
                    "description": "what do you want to know?",
                    "required": False
                }
            ]
        }
    ]

    headers = {
        "User-Agent": "beat-helper",
        "Content-Type": "application/json",
        "Authorization": f"Bot {DISCORD_TOKEN}"
    }

    for c in commands:
        requests.post(endpoint, headers=headers, json=c).raise_for_status()

def verify(signature: str, timestamp: str, body: str) -> bool:
    try:
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
    except Exception as e:
        print(f"failed to verify request: {e}")
        return False

    return True

def callback(event: dict, context: dict):
    # API Gateway has weird case conversion, so we need to make them lowercase.
    # See https://github.com/aws/aws-sam-cli/issues/1860
    headers: dict = { k.lower(): v for k, v in event['headers'].items() }
    rawBody: str = event['body']

    # validate request
    signature = headers.get('x-signature-ed25519')
    timestamp = headers.get('x-signature-timestamp')
    if not verify(signature, timestamp, rawBody):
        return {
            "cookies": [],
            "isBase64Encoded": False,
            "statusCode": 401,
            "headers": {},
            "body": ""
        }
    
    req: dict = json.loads(rawBody)
    if req['type'] == 1: # InteractionType.Ping
        registerCommands()
        return {
            "type": 1 # InteractionResponseType.Pong
        }
    elif req['type'] == 2: # InteractionType.ApplicationCommand
        # command options list -> dict
        opts = {v['name']: v['value'] for v in req['data']['options']} if 'options' in req['data'] else {}
        interactionToken = req['token']

        if not 'message' in opts:
            return {
            "type": 4, # InteractionResponseType.ChannelMessageWithSource
            "data": {
                "content": "メッセージが入力されていません."
            }
        }
        else:
            text = f"{opts['message']}"
            executor.submit(sendMessage, interactionToken, text)
            return {
                "type": 5, # InteractionResponseType.DeferredChannelMessageWithSource
                "data": {
                    "content": f"処理中…"
                }
            }
            

def sendMessage(interactionToken: str, text: str):
    url = f"{DISCORD_ENDPOINT}/webhooks/{APPLICATION_ID}/{interactionToken}"
    headers = {
        "Authorization": f"Bot {DISCORD_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "content": text
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()  # Raise an exception for HTTP errors
    return response.json()