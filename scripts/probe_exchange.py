import asyncio

import httpx
from websockets.asyncio.client import connect


async def main():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            response = await client.get("https://data-api.binance.vision/api/v3/ping")
            print("REST", response.status_code)
        except Exception as error:
            print("REST", type(error).__name__, str(error))
    for origin in ("wss://stream.binance.com:9443", "wss://data-stream.binance.vision:443"):
        try:
            async with connect(origin + "/ws/btcusdt@ticker", open_timeout=8) as socket:
                await asyncio.wait_for(socket.recv(), 8)
                print(origin, "message received")
        except Exception as error:
            print(origin, type(error).__name__, str(error))


asyncio.run(main())
