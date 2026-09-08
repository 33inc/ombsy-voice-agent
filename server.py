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

# Telnyx TeXML Webhook endpoint for Voice
@app.post("/webhook")
async def telnyx_webhook(request: Request):
    host = request.headers.get("host")
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

from google import genai
from google.genai import types
import telnyx

# Configure Gemini for SMS Agent
gemini_client = genai.Client(api_key=os.getenv("Ombsy_Gemini_Brain", os.getenv("GEMINI_API_KEY")))
telnyx.api_key = os.getenv("TELNYX_API_KEY")

# SMS Webhook endpoint
@app.post("/webhook/sms")
async def telnyx_sms_webhook(request: Request):
    try:
        body = await request.json()
        data = body.get("data", {})
        event_type = data.get("event_type")
        
        if event_type == "message.received":
            payload = data.get("payload", {})
            from_number = payload.get("from", {}).get("phone_number")
            to_number = payload.get("to", [{}])[0].get("phone_number")
            text = payload.get("text", "")
            
            logger.info(f"Received SMS from {from_number}: {text}")
            
            # Generate response via Google Jules (Gemini)
            response = await gemini_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are Google Jules, operating as the elite 'Ombsy Receptionist' for the Ombsy Capital Group. "
                        "You provide absolute best-in-class administrative support and client care via SMS. "
                        "Your tone is warm, highly professional, accommodating, and efficient. "
                        "You assist clients with queries regarding Tax Preparation, Credit Repair, Business Funding, Training, and Masterclass enrollments. "
                        "Keep your responses concise (1-2 sentences). "
                        "Never hallucinate services outside of the Ombsy ecosystem. If you do not know the answer, politely inform them an executive will follow up."
                    )
                )
            )
            reply_text = response.text.strip()
            
            logger.info(f"Google Jules reply: {reply_text}")
            
            # Send reply via Telnyx REST API to avoid SDK version conflicts
            import requests
            headers = {
                "Authorization": f"Bearer {os.getenv('TELNYX_API_KEY')}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "from": to_number,
                "to": from_number,
                "text": reply_text
            }
            res = requests.post("https://api.telnyx.com/v2/messages", headers=headers, json=payload)
            logger.info(f"Telnyx SMS send status: {res.status_code} {res.text}")
            
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Error handling SMS webhook: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# WhatsApp Webhook endpoint
@app.post("/webhook/whatsapp")
async def telnyx_whatsapp_webhook(request: Request):
    try:
        body = await request.json()
        data = body.get("data", {})
        event_type = data.get("event_type")

        if event_type == "message.received":
            payload = data.get("payload", {})
            from_number = payload.get("from", {}).get("phone_number")
            to_number = payload.get("to", [{}])[0].get("phone_number")
            text = payload.get("text", "")

            logger.info(f"Received WhatsApp from {from_number}: {text}")

            # Generate response via Google Jules (Gemini)
            response = await gemini_client.aio.models.generate_content(
                model="gemini-2.5-flash",
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=(
                        "You are Google Jules, operating as the elite 'Ombsy Receptionist' for the Ombsy Capital Group. "
                        "You provide absolute best-in-class administrative support and client care via WhatsApp. "
                        "Your tone is warm, highly professional, accommodating, and efficient. "
                        "You assist clients with queries regarding Tax Preparation, Credit Repair, Business Funding, Training, and Masterclass enrollments. "
                        "Keep your responses concise (1-3 sentences) and friendly. Feel free to use appropriate emojis. "
                        "Never hallucinate services outside of the Ombsy ecosystem. If you do not know the answer, politely inform them an executive will follow up."
                    )
                )
            )
            reply_text = response.text.strip()

            logger.info(f"Google Jules WhatsApp reply: {reply_text}")

            # Send reply via Telnyx REST API
            import requests
            headers = {
                "Authorization": f"Bearer {os.getenv('TELNYX_API_KEY')}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "from": to_number,
                "to": from_number,
                "text": reply_text
            }
            res = requests.post("https://api.telnyx.com/v2/messages", headers=headers, json=payload)
            logger.info(f"Telnyx WhatsApp send status: {res.status_code} {res.text}")

        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Error handling WhatsApp webhook: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# WebSocket endpoint for the media stream
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established with Telnyx.")
    
    try:
        # Telnyx sends a start event first, but might send 'connected' before it.
        stream_id = None
        while True:
            msg = await websocket.receive_text()
            data = json.loads(msg)
            event = data.get("event")
            
            if event == "start":
                stream_id = data.get("start", {}).get("stream_id")
                logger.info(f"Received start event for stream {stream_id}")
                break
            elif event == "connected":
                logger.info("Received connected event, waiting for start...")
                continue
            else:
                logger.warning(f"Received unexpected event before start: {event}")
                continue
                
        if stream_id:
            # Pass the actual live stream_id to Pipecat so it can route audio back properly!
            await run_bot(websocket, stream_id)
        else:
            logger.error("Failed to extract stream_id.")
            
    except Exception as e:
        logger.error(f"Error handling websocket: {e}")
    finally:
        logger.info("WebSocket disconnected.")

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
