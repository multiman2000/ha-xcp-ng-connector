# XCP-ng / Xen Orchestra for Home Assistant

Monitor an XCP-ng cluster (pool, hosts, VMs, storage) and XOA backup jobs in
Home Assistant, via the Xen Orchestra REST API. Built for a small homelab
setup (1 pool, 2 hosts, XOA-CE running as a VM doing the backups), but works
with any pool XO can see.

This is a read-only monitoring integration: it does not start/stop VMs or
hosts, or trigger backups.

## What you get

For each **pool**:
- VMs running / VMs total
- Average CPU usage across the pool's hosts
- Aggregate memory usage across the pool's hosts
- High availability enabled (binary sensor)

For each **host**:
- CPU usage (%)
- Memory usage (%, with used/total bytes as attributes)
- Uptime (last boot time)
- Power state (binary sensor)
- Maintenance mode (binary sensor)

For each **VM**:
- Memory usage (%)
- Power state (binary sensor)

For each **storage repository (SR)**:
- Space usage (%, with used/total bytes as attributes)

For each **XOA backup job**:
- Status of the last run (`success`, `failure`, `skipped`, `interrupted`,
  `pending`, `never_run`), with the run's start/end time and duration as
  attributes
- "Backup failed" binary sensor (on for `failure`/`interrupted`)

New VMs, hosts or backup jobs created after setup are picked up automatically
on the next poll — no need to reload the integration.

## Requirements

- A running Xen Orchestra instance (XOA / XOA-CE, or self-built XO) that can
  see your pool. This integration talks to XO's REST API, not directly to
  the XCP-ng hosts.
- Either an XO **API token** (Settings > API tokens in the XO web UI, or
  `xo-cli create-token`) — recommended — or an XO username/password.

## Installation

### Via HACS (recommended)

1. In HACS, add this repository as a custom repository (category:
   *Integration*) if it is not yet in the default HACS store:
   `https://github.com/multiman2000/ha-xcp-ng-connector`
2. Install "XCP-ng / Xen Orchestra" from HACS.
3. Restart Home Assistant.
4. Go to **Settings > Devices & Services > Add Integration** and search for
   "XCP-ng / Xen Orchestra".

### Manual

Copy `custom_components/xcpng` into your Home Assistant `config/custom_components`
directory and restart Home Assistant.

## Configuration

All configuration happens in the UI:

1. Enter the URL or IP address of your XOA instance (e.g. `https://xoa.local`
   or `192.168.1.10`).
2. Choose whether to verify the SSL certificate (turn this off for a
   self-signed certificate, which is the XOA default).
3. Choose an authentication method and enter the token, or username/password.

The polling interval (default 60 seconds) can be changed afterwards from the
integration's **Configure** button.

## Notes & limitations

- CPU usage is read from XO's short-term RRD stats (`/hosts/{id}/stats`) and
  is a snapshot of the most recent sample, not a long-term average.
- VM CPU usage is not exposed (to avoid one extra API call per VM on every
  poll); VM memory usage is included since it comes for free with the VM
  list.
- Backup job status is based on XO's `backup-logs`; the most recent 200 log
  entries are fetched each poll and grouped by job to find each job's latest
  run, so very old runs are never a concern but a very large log history
  is not fully retrieved.

## Contributing

Issues and PRs welcome. This was scaffolded for a specific homelab (1 pool,
2 hosts, XOA-CE), so feedback from other cluster shapes (multiple pools,
resource pools without HA, etc.) is especially useful.
