import json
payload = {
  "data": {
    "event_type": "message.received",
    "id": "3ca7bd3d-7d82-4e07-9b4f-859d0a0bf43b",
    "occurred_at": "2019-04-13T17:04:50.52+00:00",
    "payload": {
      "completed_at": None,
      "cost": None,
      "direction": "inbound",
      "encoding": "UTF-8",
      "errors": [],
      "from": {
        "carrier": "TELNYX LLC",
        "line_type": "VoIP",
        "phone_number": "+13122708200"
      },
      "id": "400171ac-ceb5-442c-a079-7a56114227d8",
      "media": [],
      "messaging_profile_id": "073dd98e-0c85-496b-970f-dd3b7aa21cce",
      "organization_id": "0dc324dc-5a21-4d1e-8bc3-eafe4d65095b",
      "parts": 1,
      "received_at": "2019-04-13T17:04:50.52+00:00",
      "record_type": "message",
      "sent_at": None,
      "tags": [],
      "text": "Hello, world!",
      "to": [
        {
          "phone_number": "+13122151743",
          "status": "webhook_delivered"
        }
      ],
      "type": "SMS",
      "valid_until": None,
      "webhook_failover_url": "https://backup.example.com/hooks",
      "webhook_url": "https://example.com/hooks"
    },
    "record_type": "event"
  },
  "meta": {
    "attempt": 1,
    "delivered_to": "https://example.com/hooks"
  }
}
print(payload["data"]["event_type"])
