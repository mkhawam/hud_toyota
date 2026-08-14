"""Smoke check: connect to /ws and print a few coalesced batches."""

import asyncio
import json
import sys

import websockets


async def main(port: int) -> None:
    async with websockets.connect(f"ws://localhost:{port}/ws") as ws:
        for i in range(4):
            batch = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            topics = batch["topics"]
            line = {t: v[0] for t, v in sorted(topics.items())}
            print(f"batch {i}: {json.dumps(line)}")


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000))
