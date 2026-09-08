import asyncio
import os
import sys

from pipecat.frames.frames import EndFrame, TextFrame, LLMMessagesAppendFrame
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

from pipecat.serializers.telnyx import TelnyxFrameSerializer

async def run_bot(websocket_client, stream_sid):
    transport = FastAPIWebsocketTransport(
        websocket=websocket_client,
        params=FastAPIWebsocketParams(
            audio_out_enabled=True,
            add_wav_header=False,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
            vad_audio_passthrough=True,
            serializer=TelnyxFrameSerializer(
                stream_id=stream_sid,
                outbound_encoding="PCMU",
                inbound_encoding="PCMU",
                params=TelnyxFrameSerializer.InputParams(auto_hang_up=False)
            )
        )
    )

    # Note: Telnyx requires SIP/RTP streaming or websocket streaming.
    # The Pipecat TelnyxTransport is usually a wrapper around standard websocket audio for Telnyx Media Streaming.
    
    llm = GeminiLiveLLMService(
        api_key=os.getenv("Ombsy_Gemini_Brain", os.getenv("GEMINI_API_KEY")),
        settings=GeminiLiveLLMService.Settings(
            model="models/gemini-2.5-flash-native-audio-latest",
            voice="Aoede"
        ),
        system_instruction=(
            "You are Google Jules, operating as the elite 'Ombsy Receptionist' for the Ombsy Capital Group. "
            "You provide absolute best-in-class administrative support and client care. "
            "Your tone is warm, highly professional, accommodating, and efficient. "
            "You assist clients with queries regarding Tax Preparation, Credit Repair, Business Funding, Training, and Masterclass enrollments. "
            "Keep your responses concise (1-2 sentences) and conversational for a voice medium. "
            "Never hallucinate services outside of the Ombsy ecosystem. If you do not know the answer, politely inform them an executive will follow up."
        )
    )

    pipeline = Pipeline(
        [
            transport.input(),
            llm,
            transport.output(),
        ]
    )

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # Kick off the conversation by prompting Gemini to greet the caller
        await task.queue_frames([
            LLMMessagesAppendFrame([
                {"role": "user", "content": "The user has just connected to the phone call. Please greet them warmly, state you are the Ombsy Receptionist, and ask how you can help them."}
            ])
        ])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        await task.queue_frames([EndFrame()])

    runner = PipelineRunner()
    
    logger.info(f"Starting pipeline for stream {stream_sid}")
    await runner.run(task)
