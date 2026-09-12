import os
import requests
from dotenv import load_dotenv

load_dotenv()
headers = {"Authorization": f"Bearer {os.getenv('TELNYX_API_KEY')}", "Content-Type": "application/json"}

# 2. Update Phone Number to use Messaging Profile
phone_payload = {"messaging_profile_id": "4001a05b-5a50-4683-91c3-a9f4fd9d0aca"}
r2 = requests.post("https://api.telnyx.com/v2/phone_numbers/3039127815468353128/messaging", headers=headers, json=phone_payload)
if r2.status_code == 405 or r2.status_code == 404:
    r2 = requests.patch("https://api.telnyx.com/v2/phone_numbers/3039127815468353128/messaging", headers=headers, json=phone_payload)

print("Phone Number Messaging Update:", r2.status_code, r2.text)
