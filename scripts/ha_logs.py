from __future__ import annotations

import asyncio
import json
import os
import sys

import websockets
from dotenv import load_dotenv


async def main() -> int:
    load_dotenv()
    url = os.environ.get("HA_URL")
    tok = os.environ.get("HA_TOKEN")
    if not (url and tok):
        print("error: HA_URL/HA_TOKEN missing", file=sys.stderr)
        return 2

    ws_url = url.replace("http://", "ws://").replace("https://", "wss://") + "/api/websocket"
    print(f"connecting to {ws_url}")

    async with websockets.connect(ws_url) as ws:
        msg = json.loads(await ws.recv())
        print(f"server: {msg}")
        await ws.send(json.dumps({"type": "auth", "access_token": tok}))
        msg = json.loads(await ws.recv())
        print(f"auth: {msg}")

        async def call(payload):
            await ws.send(json.dumps(payload))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == payload["id"]:
                    return resp

        print("\n=== config_entries/get ===")
        r = await call({"id": 1, "type": "config_entries/get", "domain": "swedish_parcels"})
        for entry in r.get("result") or []:
            print(f"  title: {entry.get('title')}")
            print(f"  state: {entry.get('state')}")
            print(f"  reason: {entry.get('reason')}")
            print(f"  source: {entry.get('source')}")

        print("\n=== system_log/list (filtered) ===")
        r = await call({"id": 2, "type": "system_log/list"})
        entries = r.get("result") or []
        if not entries:
            print(f"  empty. raw response: {r}")
        for entry in entries:
            name = entry.get("name") or ""
            msg_str = json.dumps(entry.get("message") or "")
            if "swedish_parcels" in (name + msg_str).lower() or "parcel" in (name + msg_str).lower():
                print("---")
                print(f"  level: {entry.get('level')}")
                print(f"  source: {name}")
                print(f"  message: {entry.get('message')}")
                if entry.get("exception"):
                    print(f"  exception:\n{entry['exception']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
