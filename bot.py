import asyncio
import os
import sys

from pipecat.frames.frames import EndFrame, TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketTransport,
    FastAPIWebsocketParams,
)
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService
from pipecat.audio.vad.silero import SileroVADAnalyzer

from loguru import logger
from dotenv import load_dotenv

load_dotenv()

async def run_bot(websocket_client, stream_sid):
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
        )
    )

    # Note: Telnyx requires SIP/RTP streaming or websocket streaming.
    # The Pipecat TelnyxTransport is usually a wrapper around standard websocket audio for Telnyx Media Streaming.
    
    llm = GeminiLiveLLMService(
        api_key=os.getenv("GEMINI_API_KEY"),
        voice_id="Aoede", # Voice model
        system_instruction=(
            "You are an elite AI agent representing the Ombsy Capital Group. "
            "Your role is to act as a professional, concise, and helpful receptionist or advisor. "
            "You handle queries regarding Tax Preparation, Credit Repair, and Business Funding. "
            "Keep your responses short (1-2 sentences), conversational, and highly professional. "
            "Never hallucinate services outside of the 12 Ombsy brands."
        )
    )

    pipeline = Pipeline(
        [
            transport.input(),
            llm,
            transport.output(),
        ]
    )

    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Kick off the conversation
        await task.queue_frames([TextFrame("Hello! Thank you for calling Ombsy Capital Group. How can I assist you today?")])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.queue_frames([EndFrame()])

    runner = PipelineRunner()
    
    logger.info(f"Starting pipeline for stream {stream_sid}")
    await runner.run(task)
