# NexCloud Status

Live status page for [NexCloud Enterprises](https://nexcloud.enterprises), powered by [cState](https://github.com/cstate/cstate) and built with Hugo.

**Live at [status.nexcloud.enterprises](https://status.nexcloud.enterprises)**

## Monitored services

- NexCloud Enterprises Website — https://nexcloud.enterprises
- Nexfinity Hosting — https://nexfinityhosting.com
- Community Forum — https://forum.nexcloud.enterprises
- js4u.site — https://js4u.site

Uptime is checked every 5 minutes by the [Monitor services workflow](.github/workflows/monitor.yml). When a service goes down it automatically opens an incident (`content/issues/auto-<service>.md`) and resolves it once the service responds again.

## Posting a manual incident update

Incidents live in `content/issues/` as Markdown files with YAML front matter. Create a new file, for example `content/issues/2026-08-11-database-outage.md`:

```markdown
---
title: Database outage
date: 2026-08-11 14:30:00
resolved: false
severity: down
affected:
  - NexCloud Enterprises Website
section: issue
---

*Investigating* - We are aware of an issue and are looking into it.

*Monitoring* - The service is recovering, we are watching closely.
```

Fields:

- `title` — headline of the incident *(required)*
- `date` — ISO-8601 time when the issue started *(required)*
- `resolved` — `true` or `false`
- `resolvedWhen` — ISO-8601 time when it ended (only when `resolved: true`)
- `severity` — `notice`, `disrupted`, or `down`
- `affected` — list of systems from `config.yml`
- `section` — must be `issue`

Push the file to `main` and the [Deploy workflow](.github/workflows/pages.yml) rebuilds the site automatically. Manual incidents are never overwritten by the auto-monitor (it only manages files it created, marked `automated: true`).

For scheduled maintenance, use `severity: notice` so it does not count as downtime.

## Development

Requires [Hugo](https://gohugo.io) (extended, 0.128+).

```sh
git clone --recursive https://github.com/MrRamyg/NexCloudStatus.git
cd NexCloudStatus
hugo serve
```

## Backup

The old Upptime-based status page is preserved on the `upptime-backup` branch.
