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

from pydantic import BaseModel
import requests

class LeadData(BaseModel):
    phone_number: str
    name: str

@app.post("/call-lead")
async def call_lead(lead: LeadData, request: Request):
    """
    Endpoint for Make.com to trigger an outbound call to a new lead.
    """
    host = request.headers.get("host")
    texml_url = f"https://{host}/webhook"

    headers = {
        "Authorization": f"Bearer {os.getenv('TELNYX_API_KEY')}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # We must use a verified Ombsy outbound number here.
    # Assuming the first number associated with the account, or passing a default.
    from_number = os.getenv("TELNYX_OUTBOUND_NUMBER", "+1234567890")

    payload = {
        "to": lead.phone_number,
        "from": from_number,
        "connection_id": os.getenv("TELNYX_CONNECTION_ID", ""),
        "answering_machine_detection": "detect",
        "answer_url": texml_url
    }

    try:
        res = requests.post("https://api.telnyx.com/v2/calls", headers=headers, json=payload)
        logger.info(f"Triggered outbound call to {lead.phone_number}: {res.status_code}")
        return JSONResponse({"status": "calling", "telnyx_response": res.json()})
    except Exception as e:
        logger.error(f"Error calling lead: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

from google import genai
from google.genai import types
import telnyx
import nacl.signing
import nacl.encoding
import nacl.exceptions
import base64
from fastapi import HTTPException

# Restore global config for pipecat-ai (which relies on google.generativeai under the hood for Voice)
try:
    import google.generativeai as legacy_genai
    legacy_genai.configure(api_key=os.getenv("Ombsy_Gemini_Brain", os.getenv("GEMINI_API_KEY", "dummy_key_for_build")))
except ImportError:
    pass

# Configure Gemini for SMS Agent
gemini_client = genai.Client(api_key=os.getenv("Ombsy_Gemini_Brain", os.getenv("GEMINI_API_KEY", "dummy_key_for_build")))
telnyx.api_key = os.getenv("TELNYX_API_KEY")
TELNYX_PUBLIC_KEY = os.getenv("TELNYX_PUBLIC_KEY")

async def verify_telnyx_webhook(request: Request):
    if not TELNYX_PUBLIC_KEY:
        # If no public key is configured, bypass validation (e.g. local dev)
        return
    body = await request.body()
    signature_header = request.headers.get("telnyx-signature-ed25519")
    timestamp_header = request.headers.get("telnyx-signature-ed25519-timestamp")
    if not signature_header or not timestamp_header:
        raise HTTPException(status_code=400, detail="Missing signature headers")
    try:
        verify_key = nacl.signing.VerifyKey(TELNYX_PUBLIC_KEY, encoder=nacl.encoding.Base64Encoder)
        payload = timestamp_header.encode('utf-8') + b'|' + body
        signature = base64.b64decode(signature_header)
        verify_key.verify(payload, signature)
    except nacl.exceptions.BadSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Make.com Integration Helper
async def send_to_make_webhook(channel: str, sender: str, incoming_text: str, ai_reply: str):
    """
    Sends the interaction data to the Make.com webhook so the user can
    store records or trigger marketing/CRM workflows.
    """
    make_webhook_url = os.getenv("MAKE_WEBHOOK_URL")
    if not make_webhook_url:
        return

    payload = {
        "channel": channel,
        "sender": sender,
        "incoming_text": incoming_text,
        "ai_reply": ai_reply
    }
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.post(make_webhook_url, json=payload)
            logger.info(f"Interaction logged to Make.com via {channel}")
    except Exception as e:
        logger.error(f"Failed to send data to Make.com: {e}")

# SMS Webhook endpoint
@app.post("/webhook/sms")
async def telnyx_sms_webhook(request: Request):
    await verify_telnyx_webhook(request)
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
            
            # Send reply via Telnyx REST API (async to avoid blocking the event loop)
            import httpx
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
            async with httpx.AsyncClient() as client:
                res = await client.post("https://api.telnyx.com/v2/messages", headers=headers, json=payload)
                logger.info(f"Telnyx SMS send status: {res.status_code} {res.text}")

            # Log interaction to Make.com
            await send_to_make_webhook("sms", from_number, text, reply_text)
            
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Error handling SMS webhook: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Email Webhook endpoint (e.g. SendGrid Inbound Parse)
@app.post("/webhook/email")
async def email_webhook(request: Request):
    try:
        # Example using SendGrid multipart/form-data
        form = await request.form()
        text = form.get("text", "")
        from_email = form.get("from", "")
        to_email = form.get("to", "")

        if not text or not from_email:
            return JSONResponse({"status": "ignored - no text or sender"})

        logger.info(f"Received Email from {from_email}")

        # Generate response via Google Jules (Gemini)
        response = await gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=text,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are Google Jules, operating as the elite 'Ombsy Receptionist' for the Ombsy Capital Group. "
                    "You provide absolute best-in-class administrative support and client care via Email. "
                    "Your tone is warm, highly professional, accommodating, and efficient. "
                    "You assist clients with queries regarding Tax Preparation, Credit Repair, Business Funding, Training, and Masterclass enrollments. "
                    "Keep your responses concise but professional. "
                    "Never hallucinate services outside of the Ombsy ecosystem. If you do not know the answer, politely inform them an executive will follow up."
                )
            )
        )
        reply_text = response.text.strip()

        logger.info(f"Google Jules Email reply generated.")

        # Here you would integrate with an Email API (like SendGrid) to send the reply_text back.
        # For example, using httpx to hit the SendGrid Mail Send API.

        # Log interaction to Make.com
        await send_to_make_webhook("email", from_email, text, reply_text)

        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Error handling Email webhook: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Facebook Messenger & Instagram Webhook endpoint (Meta Graph API)
@app.get("/webhook/facebook")
async def facebook_webhook_verify(request: Request):
    # Meta verification step
    verify_token = os.getenv("META_VERIFY_TOKEN", "ombsy_default_verify_token")
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == verify_token:
        return Response(content=challenge, media_type="text/plain")
    return JSONResponse({"error": "Invalid verification token"}, status_code=403)

@app.post("/webhook/facebook")
async def facebook_webhook_receive(request: Request):
    try:
        body = await request.json()

        # Determine if it's a page or instagram webhook
        if body.get("object") in ["page", "instagram"]:
            for entry in body.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    sender_id = messaging_event.get("sender", {}).get("id")
                    text = messaging_event.get("message", {}).get("text", "")

                    if text:
                        logger.info(f"Received Social Media Message from {sender_id}: {text}")

                        # Generate response via Google Jules (Gemini)
                        response = await gemini_client.aio.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=text,
                            config=types.GenerateContentConfig(
                                system_instruction=(
                                    "You are Google Jules, operating as the elite 'Ombsy Receptionist' for the Ombsy Capital Group. "
                                    "You provide absolute best-in-class administrative support and client care via Facebook and Instagram. "
                                    "Your tone is warm, highly professional, accommodating, and efficient. "
                                    "You assist clients with queries regarding Tax Preparation, Credit Repair, Business Funding, Training, and Masterclass enrollments. "
                                    "Keep your responses concise, friendly, and use appropriate emojis. "
                                    "Never hallucinate services outside of the Ombsy ecosystem. If you do not know the answer, politely inform them an executive will follow up."
                                )
                            )
                        )
                        reply_text = response.text.strip()

                        logger.info(f"Google Jules Social Media reply: {reply_text}")

                        # Here you would integrate with the Meta Graph API to send the reply_text back using the PAGE_ACCESS_TOKEN.

                        # Log interaction to Make.com
                        await send_to_make_webhook("social", sender_id, text, reply_text)

        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"Error handling Facebook webhook: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# WhatsApp Webhook endpoint
@app.post("/webhook/whatsapp")
async def telnyx_whatsapp_webhook(request: Request):
    await verify_telnyx_webhook(request)
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

            # Send reply via Telnyx REST API (async to avoid blocking the event loop)
            import httpx
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
            async with httpx.AsyncClient() as client:
                res = await client.post("https://api.telnyx.com/v2/messages", headers=headers, json=payload)
                logger.info(f"Telnyx WhatsApp send status: {res.status_code} {res.text}")

            # Log interaction to Make.com
            await send_to_make_webhook("whatsapp", from_number, text, reply_text)

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
