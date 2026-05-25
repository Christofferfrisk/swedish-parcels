from __future__ import annotations

import json
import os
import sys

import httpx
from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    url = os.environ.get("HA_URL")
    token = os.environ.get("HA_TOKEN")
    if not (url and token):
        print("error: set HA_URL and HA_TOKEN in .env", file=sys.stderr)
        return 2

    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}

    try:
        with httpx.Client(timeout=10.0, headers=headers) as c:
            r = c.get(f"{url}/api/")
            r.raise_for_status()
            print(f"connected: {r.json().get('message')}")

            r = c.get(f"{url}/api/config")
            cfg = r.json()
            print(f"ha version: {cfg.get('version')}")

            r = c.get(f"{url}/api/services")
            services = r.json()
            domain_present = any(s.get("domain") == "swedish_parcels" for s in services)
            print(f"swedish_parcels domain registered: {domain_present}")

            r = c.get(f"{url}/api/states")
            states = r.json()
    except httpx.HTTPError as e:
        print(f"http error: {e}", file=sys.stderr)
        return 1

    parcel_states = [
        s for s in states
        if "swedish_parcels" in s["entity_id"] or "parcel" in s["entity_id"].lower()
    ]

    print(f"\nfound {len(parcel_states)} parcel-related entities:")
    if not parcel_states:
        print("  (none — integration may not be installed/loaded yet)")
        sensor_count = sum(1 for s in states if s["entity_id"].startswith("sensor."))
        print(f"\ndebug: HA has {len(states)} total entities ({sensor_count} sensors).")
        first_sensors = [s for s in states if s["entity_id"].startswith("sensor.")][:5]
        for s in first_sensors:
            print(f"  {s['entity_id']} = {s['state']}")
        return 0

    for s in parcel_states:
        print(f"\n--- {s['entity_id']}")
        print(f"  state: {s['state']}")
        for k, v in (s.get("attributes") or {}).items():
            if k in ("friendly_name", "icon"):
                continue
            print(f"  {k}: {_short(v)}")
    return 0


def _short(v: object, n: int = 100) -> str:
    text = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return text if len(text) <= n else text[: n - 1] + "…"


if __name__ == "__main__":
    raise SystemExit(main())
