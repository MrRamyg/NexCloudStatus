#!/usr/bin/env python3
"""
NexCloud Status auto-monitor.

Checks each configured service and, when a service is unreachable,
creates or resolves the corresponding cState incident file under
content/issues/. Only files this script owns (front matter with
automated: true and id matching the system) are touched, so manual
incidents written by humans are never overwritten.
"""

import datetime
import glob
import os
import re
import ssl
import sys
import urllib.error
import urllib.request

ISSUES_DIR = os.path.join("content", "issues")
CHECK_TIMEOUT = 20
RECREATE_COOLDOWN_MIN = 30

SYSTEMS = [
    {"name": "NexCloud Enterprises Website", "url": "https://nexcloud.enterprises"},
    {"name": "Nexfinity Hosting", "url": "https://nexfinityhosting.com"},
    {"name": "Community Forum", "url": "https://forum.nexcloud.enterprises"},
    {"name": "js4u.site", "url": "https://js4u.site"},
]


def slugify(name):
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def utcnow():
    return datetime.datetime.now(datetime.timezone.utc)


def fmt_iso(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def fmt_iso_z(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def is_up(url):
    req = urllib.request.Request(url, headers={"User-Agent": "NexCloudStatusBot/1.0"})
    try:
        with urllib.request.urlopen(
            req, timeout=CHECK_TIMEOUT, context=ssl.create_default_context()
        ) as resp:
            return 200 <= resp.status < 400
    except urllib.error.HTTPError as err:
        return 200 <= err.code < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def split_front_matter(path):
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    m = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)$", raw, re.S)
    if not m:
        return None, raw
    return m.group(1), m.group(2)


def parse_bool(value):
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "yes", "1")


def load_incidents():
    incidents = []
    for path in glob.glob(os.path.join(ISSUES_DIR, "**", "*.md"), recursive=True):
        name = os.path.basename(path)
        if name == ".gitkeep":
            continue
        fm, _ = split_front_matter(path)
        if fm is None:
            continue
        affected = []
        m = re.search(r"^affected:\s*(\[[^\]]*\]|.*)$", fm, re.M)
        if m:
            block = m.group(1)
            if block.startswith("["):
                for item in re.findall(r"\"([^\"]*)\"|'([^']*)'|([A-Za-z0-9 _./-]+)", block):
                    val = item[0] or item[1] or item[2]
                    val = val.strip()
                    if val:
                        affected.append(val)
            else:
                for line in re.findall(r"^  -\s*(.+)$", fm[m.start():], re.M):
                    affected.append(line.strip())
        resolved = parse_bool(
            re.search(r"^resolved:\s*(.+)$", fm, re.M).group(1)
            if re.search(r"^resolved:\s*(.+)$", fm, re.M)
            else "false"
        )
        automated = parse_bool(
            re.search(r"^automated:\s*(.+)$", fm, re.M).group(1)
            if re.search(r"^automated:\s*(.+)$", fm, re.M)
            else "false"
        )
        date_raw = re.search(r"^date:\s*(.+)$", fm, re.M)
        date = None
        if date_raw:
            try:
                date = datetime.datetime.fromisoformat(date_raw.group(1).strip().strip("'\""))
            except ValueError:
                try:
                    date = datetime.datetime.strptime(
                        date_raw.group(1).strip().strip("'\""), "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=datetime.timezone.utc)
                except ValueError:
                    date = None
        incidents.append(
            {
                "path": path,
                "affected": affected,
                "resolved": resolved,
                "automated": automated,
                "date": date,
                "front_matter": fm,
            }
        )
    return incidents


def write_auto_incident(system, detected):
    slug = slugify(system["name"])
    fm = [
        "---",
        "title: %s is down" % system["name"],
        "date: %s" % fmt_iso(detected),
        "resolved: false",
        "severity: down",
        "affected:",
        "  - %s" % system["name"],
        "automated: true",
        "id: %s" % slug,
        "section: issue",
        "---",
        "",
        "*Automated check detected that the %s service is unreachable.* "
        "We are investigating." % system["name"],
        "",
        "**Detected** - The service stopped responding to checks. "
        "{{< track \"%s\" >}}" % fmt_iso_z(detected),
        "",
    ]
    path = os.path.join(ISSUES_DIR, "auto-%s.md" % slug)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(fm))


def resolve_auto_incident(incident, resolved_at):
    body = (
        "*Automated check confirmed that the service is responding again. "
        "No further action is required.*\n"
    )
    fm = re.sub(r"^resolved:\s*.*$", "resolved: true", incident["front_matter"], count=1, flags=re.M)
    fm = re.sub(
        r"^resolvedWhen:\s*.*$", "", fm, count=1, flags=re.M
    )
    new_content = "---\n%s\nresolvedWhen: %s\n---\n\n%s" % (fm, fmt_iso(resolved_at), body)
    with open(incident["path"], "w", encoding="utf-8") as fh:
        fh.write(new_content)


def main():
    incidents = load_incidents()
    now = utcnow()
    changed = False

    for system in SYSTEMS:
        name = system["name"]
        up = is_up(system["url"])

        unresolved = [i for i in incidents if name in i["affected"] and not i["resolved"]]
        auto_unresolved = [i for i in unresolved if i["automated"]]
        auto_resolved_recent = [
            i
            for i in incidents
            if name in i["affected"]
            and i["automated"]
            and i["resolved"]
            and i["date"] is not None
            and (now - i["date"]).total_seconds() < RECREATE_COOLDOWN_MIN * 60
        ]

        if up:
            for incident in auto_unresolved:
                print("[up] resolving auto incident %s" % os.path.basename(incident["path"]))
                resolve_auto_incident(incident, now)
                changed = True
        else:
            if not unresolved and not auto_resolved_recent:
                print("[down] creating auto incident for %s" % name)
                write_auto_incident(system, now)
                changed = True
            else:
                print("[down] %s already has an active incident, skipping" % name)

    if not changed:
        print("no changes")
    sys.exit(0)


if __name__ == "__main__":
    main()
