import requests

payload = {
  "data": {
    "event_type": "message.received",
    "payload": {
      "to": [{"phone_number": "+13187351988"}],
      "from": {"phone_number": "+13122151743"},
      "text": "Hello Jules, who are you?"
    }
  }
}
r = requests.post("http://localhost:8000/webhook/sms", json=payload)
print(r.status_code)
print(r.text)
