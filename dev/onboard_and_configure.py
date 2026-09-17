"""Drive a fresh Home Assistant instance through onboarding and set up the
xcpng integration against the mock XOA server, entirely via HTTP.

Usage (with the docker-compose stack in this folder running):
    pip install aiohttp
    python onboard_and_configure.py

Useful for smoke-testing this integration end-to-end without clicking
through the UI by hand.
"""
import asyncio
import sys

import aiohttp

HA_BASE = "http://127.0.0.1:8123"
XOA_BASE = "http://mock-xoa:18765"  # HA-internal hostname inside docker-compose


async def main():
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{HA_BASE}/api/onboarding/users",
            json={
                "client_id": HA_BASE + "/",
                "name": "Test User",
                "username": "test",
                "password": "test12345",
                "language": "en",
            },
        ) as resp:
            print("onboarding/users status", resp.status)
            data = await resp.json()
            auth_code = data["auth_code"]

        async with session.post(
            f"{HA_BASE}/auth/token",
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "client_id": HA_BASE + "/",
            },
        ) as resp:
            token_data = await resp.json()
            access_token = token_data["access_token"]

        headers = {"Authorization": f"Bearer {access_token}"}

        await session.post(f"{HA_BASE}/api/onboarding/core_config", headers=headers)
        await session.post(
            f"{HA_BASE}/api/onboarding/integration",
            headers=headers,
            json={"client_id": HA_BASE + "/", "redirect_uri": HA_BASE + "/"},
        )

        async with session.post(
            f"{HA_BASE}/api/config/config_entries/flow",
            headers=headers,
            json={"handler": "xcpng", "show_advanced_options": False},
        ) as resp:
            flow = await resp.json()
            flow_id = flow["flow_id"]

        async with session.post(
            f"{HA_BASE}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={"host": XOA_BASE, "verify_ssl": False, "auth_method": "token"},
        ) as resp:
            step = await resp.json()
            flow_id = step.get("flow_id", flow_id)

        async with session.post(
            f"{HA_BASE}/api/config/config_entries/flow/{flow_id}",
            headers=headers,
            json={"api_token": "fake-token-for-testing"},
        ) as resp:
            result = await resp.json()
            print(result)

        if result.get("type") != "create_entry":
            print("FAILED: config entry was not created")
            sys.exit(1)

        async with session.get(f"{HA_BASE}/api/states", headers=headers) as resp:
            states = await resp.json()
            for s in sorted(states, key=lambda s: s["entity_id"]):
                if s["entity_id"].startswith(("sensor.", "binary_sensor.")):
                    print(f"  {s['entity_id']:45s} = {s['state']!r}")

        print("DONE")


asyncio.run(main())
