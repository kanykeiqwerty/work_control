# import requests
# from decouple import config

# BOT_TOKEN=config('BOT_TOKEN')
# CHAT_ID=config('CHAT_ID')



# def send_message(text: str):
#     url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

#     payload = {
#         "chat_id": CHAT_ID,
#         "text": text,
#         "parse_mode": "HTML"
#     }

#     response = requests.post(url, json=payload)

#     if response.status_code != 200:
#         raise Exception(f"Telegram error: {response.text}")
    

import requests
from decouple import config

BOT_TOKEN = config('BOT_TOKEN')

CHAT_IDS = [
    config('CHAT_ID_1'),
    config('CHAT_ID_2'),
]

def send_message(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    for chat_id in CHAT_IDS:
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }

        response = requests.post(url, json=payload)

        if response.status_code != 200:
            print(f"Telegram error for {chat_id}: {response.text}")