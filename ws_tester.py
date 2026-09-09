import asyncio
import websockets
import json

async def test():
    try:
        async with websockets.connect('ws://localhost:8000/ws') as ws:
            print("Connected! Sending start event...")
            await ws.send(json.dumps({"event": "start", "start": {"stream_id": "test_stream_123"}}))
            print("Sent! Waiting for message...")
            res = await ws.recv()
            print("Received:", res)
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(test())
