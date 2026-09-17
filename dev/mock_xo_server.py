"""Minimal fake Xen Orchestra REST API server for testing the xcpng
Home Assistant integration end-to-end without a real XCP-ng cluster.

Standard library + aiohttp only. Run directly, or via the docker-compose
setup in this folder (`docker compose up`).
"""
from aiohttp import web

POOL = {
    "id": "pool1",
    "name_label": "Homelab Pool",
    "name_description": "",
    "master": "host1",
    "HA_enabled": True,
    "cpus": {"cores": 8},
    "tags": [],
}

HOSTS = [
    {
        "id": "host1", "name_label": "xcp-host-1", "power_state": "Running", "enabled": True,
        "memory": {"size": 34223104000, "usage": 12000000000}, "cpus": {"cores": 8},
        "address": "10.0.0.11", "startTime": 1758000000, "$pool": "pool1",
        "productBrand": "XCP-ng", "version": "8.3.0",
    },
    {
        "id": "host2", "name_label": "xcp-host-2", "power_state": "Running", "enabled": True,
        "memory": {"size": 34223104000, "usage": 9000000000}, "cpus": {"cores": 8},
        "address": "10.0.0.12", "startTime": 1758000500, "$pool": "pool1",
        "productBrand": "XCP-ng", "version": "8.3.0",
    },
]

VMS = [
    {
        "id": "vm1", "name_label": "xoa-ce", "power_state": "Running",
        "memory": {"size": 2147483648, "usage": 1073741824}, "CPUs": {"number": 2},
        "$container": "host1", "$pool": "pool1", "tags": [],
    },
    {
        "id": "vm2", "name_label": "nextcloud", "power_state": "Running",
        "memory": {"size": 4294967296, "usage": 3000000000}, "CPUs": {"number": 2},
        "$container": "host2", "$pool": "pool1", "tags": [],
    },
    {
        "id": "vm3", "name_label": "test-vm-off", "power_state": "Halted",
        "memory": {"size": 1073741824, "usage": 0}, "CPUs": {"number": 1},
        "$container": "pool1", "$pool": "pool1", "tags": [],
    },
]

SRS = [
    {
        "id": "sr1", "name_label": "Local storage (host1)", "physical_usage": 200000000000,
        "size": 500000000000, "$container": "host1", "content_type": "user", "shared": False,
    },
    {
        "id": "sr2", "name_label": "Shared NFS", "physical_usage": 900000000000,
        "size": 2000000000000, "$container": "pool1", "content_type": "user", "shared": True,
    },
]

BACKUP_JOBS = [{"id": "job1", "name": "Daily VM Backup"}]
BACKUP_LOGS = [
    {"id": "log2", "status": "success", "start": 1758100000000, "end": 1758100300000, "jobId": "job1"},
    {"id": "log1", "status": "failure", "start": 1758013600000, "end": 1758013900000, "jobId": "job1"},
]


def project(obj, fields):
    if not fields:
        return obj
    keys = fields.split(",")
    return {k: obj.get(k) for k in keys}


async def handle(request: web.Request):
    fields = request.query.get("fields")
    path = request.path

    if path == "/rest/v0/pools":
        return web.json_response([project(POOL, fields)])
    if path == "/rest/v0/hosts":
        return web.json_response([project(h, fields) for h in HOSTS])
    if path == "/rest/v0/vms":
        return web.json_response([project(v, fields) for v in VMS])
    if path == "/rest/v0/srs":
        return web.json_response([project(s, fields) for s in SRS])
    if path == "/rest/v0/backup-jobs":
        return web.json_response([project(j, fields) for j in BACKUP_JOBS])
    if path == "/rest/v0/backup-logs":
        return web.json_response([project(l, fields) for l in BACKUP_LOGS])
    for h in HOSTS:
        if path == f"/rest/v0/hosts/{h['id']}/stats":
            return web.json_response({
                "endTimestamp": 1758100300,
                "interval": 5,
                "stats": {"cpus": {"0": [1.2, 2.1, 3.4], "1": [4.5, 5.6, 6.7]}},
            })
    return web.json_response({"error": f"not found: {path}"}, status=404)


def make_app():
    app = web.Application()
    app.router.add_get("/{tail:.*}", handle)
    return app


if __name__ == "__main__":
    web.run_app(make_app(), host="0.0.0.0", port=18765)
