import os
import json
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import JSONResponse
import uvicorn
from loguru import logger
from bot import run_bot
from dotenv import load_dotenv
import asyncio

load_dotenv()

app = FastAPI()

# Telnyx TeXML Webhook endpoint
@app.post("/webhook")
async def telnyx_webhook(request: Request):
    # For TeXML applications, Telnyx hits this URL when the phone number is dialed.
    # We simply reply with TeXML instructing Telnyx to stream the audio to our WebSocket.
    
    host = request.headers.get("host")
    # For local testing with ngrok, host will be your ngrok domain
    ws_url = f"wss://{host}/ws"
    
    texml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{ws_url}" />
    </Connect>
</Response>
"""
    from fastapi.responses import Response
    logger.info("Incoming call received! Replying with TeXML to establish Media Stream...")
    return Response(content=texml, media_type="text/xml")

# WebSocket endpoint for the media stream
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established with Telnyx.")
    
    # Run the Pipecat bot pipeline
    try:
        await run_bot(websocket, "telnyx_stream")
    except Exception as e:
        logger.error(f"Error running pipecat bot: {e}")
    finally:
        logger.info("WebSocket disconnected.")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
