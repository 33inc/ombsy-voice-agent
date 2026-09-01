import asyncio
import websockets

async def test():
    print("Connecting...")
    try:
        async with websockets.connect('ws://localhost:8000/ws') as ws:
            print("Connected! Waiting for message...")
            res = await ws.recv()
            print("Received:", res)
    except Exception as e:
        print("Error:", e)

asyncio.run(test())
