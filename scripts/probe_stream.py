import asyncio
import json
import time

from websockets.asyncio.client import connect

from shepard_engine.ingestion import stream_url
from shepard_engine.settings import get_settings


async def main():
    settings = get_settings()
    async with connect(stream_url(settings.symbol_set), open_timeout=10) as socket:
        for _ in range(3):
            message = json.loads(await asyncio.wait_for(socket.recv(), 10))
            data = message.get("data", message)
            print(
                json.dumps(
                    {
                        "stream": message.get("stream"),
                        "e": data.get("e"),
                        "s": data.get("s"),
                        "E": data.get("E"),
                        "now_ms": int(time.time() * 1000),
                        "keys": list(data),
                    }
                )
            )


asyncio.run(main())
