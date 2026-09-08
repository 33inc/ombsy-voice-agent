import asyncio
import websockets
import json

async def test_ws():
    uri = 'ws://localhost:8000/ws'
    try:
        async with websockets.connect(uri) as ws:
            print('Connected to ws')
            
            # Send connected event
            await ws.send(json.dumps({'event': 'connected', 'protocol': 'telnyx', 'version': '1.0.0'}))
            print('Sent connected')
            await asyncio.sleep(0.5)
            
            # Send start event
            await ws.send(json.dumps({
                'event': 'start',
                'start': {
                    'stream_id': 'test-stream-id-12345',
                    'call_control_id': 'mock-call-control'
                }
            }))
            print('Sent start')
            
            # Now wait for incoming messages (media frames)
            while True:
                msg = await ws.recv()
                data = json.loads(msg)
                print('Received event:', data.get('event'))
                if data.get('event') == 'media':
                    print('Got AUDIO data!')
                    break
    except Exception as e:
        print('Error:', e)

asyncio.run(test_ws())
