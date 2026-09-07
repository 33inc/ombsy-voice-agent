import os
from fastapi import FastAPI, Response
import uvicorn

app = FastAPI()

@app.post("/webhook")
async def telnyx_webhook():
    texml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Hello! The Telnyx connection is completely successful. Your voice agent is currently offline for maintenance.</Say>
</Response>
"""
    return Response(content=texml, media_type="text/xml")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)
