# Local dev/test stack

Spins up a real Home Assistant container plus a fake Xen Orchestra REST API
(`mock_xo_server.py`, simulating 1 pool / 2 hosts / 3 VMs / 2 SRs / 1 backup
job), so the `xcpng` integration can be exercised end-to-end without a real
XCP-ng cluster. Requires Docker (or Podman with `podman compose`).

## Run it

```sh
cd dev
docker compose up -d
```

Then either:

- Open http://localhost:8123, click through onboarding, add the
  "XCP-ng / Xen Orchestra" integration, and use `http://mock-xoa:18765` as
  the host (any string as the API token — the mock server doesn't check
  auth), or
- Run the scripted version, which does the same thing over HTTP and prints
  every resulting entity's state:

  ```sh
  pip install aiohttp
  python onboard_and_configure.py
  ```

Expected result: the config entry reaches state `loaded`, and 29
sensor/binary_sensor entities appear (pool CPU/memory, per-host CPU/memory/
uptime, VM power/memory, SR usage, and the backup job's status).

## Tear down

```sh
docker compose down -v
```

The `-v` also drops the `ha-config` volume, so the next `up` starts from a
clean onboarding state.
