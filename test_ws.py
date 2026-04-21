import asyncio
import websockets
import json

async def test_ws():
    uri = "ws://localhost:8000/ws"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"cmd": "start"}))
        for _ in range(10):
            msg = await ws.recv()
            data = json.loads(msg)
            if "frame_b64" in data:
                b64 = data["frame_b64"]
                print(f"Received frame_b64 length: {len(b64)}")
                print(f"Starts with: {b64[:30]}")
                if len(b64) > 0:
                    break

asyncio.run(test_ws())
