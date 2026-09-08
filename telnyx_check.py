import os
import requests
from dotenv import load_dotenv

load_dotenv()
headers = {"Authorization": f"Bearer {os.getenv('TELNYX_API_KEY')}"}

print('--- Phone Numbers ---')
res = requests.get('https://api.telnyx.com/v2/phone_numbers', headers=headers)
print(res.json())

print('\n--- TeXML Apps ---')
res = requests.get('https://api.telnyx.com/v2/texml_applications', headers=headers)
print(res.json())

print('\n--- Messaging Profiles ---')
res = requests.get('https://api.telnyx.com/v2/messaging_profiles', headers=headers)
print(res.json())
