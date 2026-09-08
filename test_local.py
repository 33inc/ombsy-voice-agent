import asyncio
import websockets

async def test():
    async with websockets.connect('ws://localhost:8000/ws') as ws:
        print("Connected")
        await asyncio.sleep(2)

asyncio.run(test())
