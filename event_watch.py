"""Recruiting events: python -m careers.event_watch [--dry-run] [--twice]."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from .event_sources import Event, SOURCES, fetch, timestamp

ROOT = Path(__file__).resolve().parent


def connect(path):
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            company TEXT, id TEXT, source TEXT NOT NULL, payload TEXT NOT NULL,
            signature TEXT NOT NULL, revision INTEGER NOT NULL, active INTEGER NOT NULL,
            PRIMARY KEY(company, id)
        );
        CREATE TABLE IF NOT EXISTS deliveries (
            company TEXT, id TEXT, revision INTEGER, payload TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(company, id, revision)
        );
        CREATE TABLE IF NOT EXISTS health (
            source TEXT PRIMARY KEY, failures INTEGER NOT NULL, alerted INTEGER NOT NULL DEFAULT 0
        );
    """)
    return db


def signature(event):
    # Ignore cosmetic copy changes on event feeds; watch substantive logistics.
    fields = ("status", "start", "when", "deadline", "location", "url")
    if event.kind == "announcement":
        fields = ("details",)
    return hashlib.sha256(json.dumps({k: event.payload()[k] for k in fields},
                                    sort_keys=True).encode()).hexdigest()


def observe(db, source, events, now):
    present = set()
    with db:
        for event in events:
            present.add((event.company, event.id))
            data = json.dumps(event.payload(), sort_keys=True)
            sig, active = signature(event), int(event.actionable(now))
            old = db.execute("SELECT signature, revision, active, source, payload FROM events WHERE company=? AND id=?",
                             (event.company, event.id)).fetchone()
            changed = old is None or old[0] != sig or (active and not old[2])
            if (old and event.kind == "community" and old[3] != source and event.status == "listed"
                    and timestamp(json.loads(old[4]).get("start")) == timestamp(event.start)):
                # Switching from rich discovery data to a bare calendar isn't a
                # reopening or venue change; avoid a second alert for the same event.
                changed = False
            revision = (old[1] + int(changed)) if old else 1
            if changed or not active:
                db.execute("UPDATE deliveries SET state='superseded' WHERE company=? AND id=? AND state IN ('pending','missing')",
                           (event.company, event.id))
            elif active:
                db.execute("UPDATE deliveries SET state='pending' WHERE company=? AND id=? AND state='missing'",
                           (event.company, event.id))
            # Announcements need a baseline. Real currently-actionable events do not.
            if active and changed and (old is not None or event.kind != "announcement"):
                db.execute("INSERT INTO deliveries(company,id,revision,payload) VALUES(?,?,?,?)",
                           (event.company, event.id, revision, data))
            db.execute("INSERT OR REPLACE INTO events VALUES(?,?,?,?,?,?,?)",
                       (event.company, event.id, source, data, sig, revision, active))
        # Don't send stale queued links which vanished from a successful source fetch.
        # Retain the seen signature, so a transient disappearance won't cause a storm.
        for company, event_id in db.execute("SELECT company,id FROM events WHERE source=?", (source,)):
            if (company, event_id) not in present:
                db.execute("UPDATE deliveries SET state='missing' WHERE company=? AND id=? AND state='pending'",
                           (company, event_id))


def format_event(event):
    if event.kind == "announcement":
        return (f"{event.company}: recruiting-event page update\n"
                "Announcement change only — date, signup availability and eligibility are NOT verified.\n"
                f"{event.details[:2400]}\nReview: {event.url}")
    if event.kind == "community":
        return (f"{event.company}: {event.title}\n{event.when} | {event.location}\n"
                f"{event.cost} | {'Waitlist' if event.status == 'waitlist' else 'Check registration'}\n"
                f"{event.eligibility}\n{event.url}")
    status = {"open": "Applications open (source deadline is in the future)",
              "listed": "Upcoming listing; confirm registration availability on the linked page",
              "waitlist": "Waitlist"}[event.status]
    return (f"{event.company}: {event.title}\n"
            f"When: {event.when}\nWhere: {event.location}\n"
            f"Status: {status}\nDeadline: {event.deadline or 'Not published'}\n"
            f"Eligibility: {event.eligibility} (confirm full requirements on source)\nCost: {event.cost}\n"
            f"{event.details[:1600]}\nSignup / details: {event.url}")


def deliver(db, now, successful_sources, sender):
    rows = db.execute("""SELECT d.company,d.id,d.revision,d.payload,e.source FROM deliveries d
        JOIN events e ON e.company=d.company AND e.id=d.id
        WHERE d.state='pending' ORDER BY d.company,d.id""").fetchall()
    ready = []
    for company, event_id, revision, payload, source in rows:
        event = Event(**json.loads(payload))
        if not event.actionable(now):
            with db:
                db.execute("UPDATE deliveries SET state='expired' WHERE company=? AND id=? AND revision=?",
                           (company, event_id, revision))
        elif source in successful_sources:
            ready.append((company, event_id, revision, event))
    sent = 0
    # Compact community listings can share a larger digest; recruiting keeps detail.
    groups = [([r for r in ready if r[3].kind != "community"], 25),
              ([r for r in ready if r[3].kind == "community"], 100)]
    batches = [rows[offset:offset + size] for rows, size in groups
               for offset in range(0, len(rows), size)]
    for batch in batches:
        keys = [(c, i, r) for c, i, r, _ in batch]
        with db:
            db.executemany("UPDATE deliveries SET attempts=attempts+1 WHERE company=? AND id=? AND revision=?", keys)
        prefix = "Community & career alerts" if any(e.kind == "community" for _, _, _, e in batch) else "Recruiting alerts"
        subject = f"{prefix}: {len(batch)} new or updated events / announcements"
        body = ("Career & community event monitor\nVirtual and in-person. "
                "Check each source for eligibility and registration details.\n\n" +
                "\n\n--------------------\n\n".join(format_event(e) for _, _, _, e in batch))
        sender(subject, body)  # failure preserves pending state for the next poll
        with db:
            db.executemany("UPDATE deliveries SET state='sent' WHERE company=? AND id=? AND revision=?", keys)
        sent += len(batch)
    return sent


def report_health(db, results, sender):
    for source, success in results.items():
        old = db.execute("SELECT failures,alerted FROM health WHERE source=?", (source,)).fetchone() or (0, 0)
        failures, alerted = (0 if success else old[0] + 1), old[1]
        with db:
            db.execute("INSERT OR REPLACE INTO health VALUES(?,?,?)", (source, failures, alerted))
        if failures >= 3 and not alerted:
            sender("Recruiting monitor: source needs attention",
                   f"{source} has failed {failures} consecutive polls. Other sources continue. "
                   "Coverage for this source is interrupted; inspect event-poller.service logs.")
            with db:
                db.execute("UPDATE health SET alerted=1 WHERE source=?", (source,))
        elif success and alerted:
            sender("Recruiting monitor: source recovered", f"{source} is fetching successfully again.")
            with db:
                db.execute("UPDATE health SET alerted=0 WHERE source=?", (source,))


def collect(sources):
    results, failures = {}, {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(fetch, source): source for source in sources}
        for future in as_completed(futures):
            source = futures[future]
            try:
                results[source.key] = future.result()
            except Exception as exc:
                # No response bodies / credentials in logs.
                failures[source.key] = type(exc).__name__
    # Feed overlap is common (e.g. AI discovery + Tech discovery + Tech Week).
    # Deterministic precedence prevents metadata differences flipping each poll.
    seen = set()
    for source in sources:
        if source.key not in results:
            continue
        unique = []
        for event in results[source.key]:
            key = (event.company, event.id)
            if key not in seen:
                unique.append(event)
                seen.add(key)
        results[source.key] = unique
    return results, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="No database writes or emails")
    parser.add_argument("--twice", action="store_true", help="Dry-run twice and check stable IDs")
    parser.add_argument("--source", action="append", choices=[s.key for s in SOURCES])
    args = parser.parse_args()
    if args.twice and not args.dry_run:
        parser.error("--twice requires --dry-run")
    sources = [s for s in SOURCES if not args.source or s.key in args.source]
    now = datetime.now(timezone.utc)
    # Dry runs don't even create a lock file; live manual and timer runs serialize.
    lock = None
    if not args.dry_run:
        lock = (ROOT / ".event-poller.lock").open("a")
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print("Another event poll is running")
            return 0
    results, failures = collect(sources)
    for source in sources:
        if source.key in failures:
            print(f"ERROR {source.key}: {failures[source.key]}", flush=True)
            continue
        events = results[source.key]
        actionable = [e for e in events if e.kind != "announcement" and e.actionable(now)]
        print(f"{source.key}: {len(events)} records, {len(actionable)} upcoming opportunities", flush=True)
        if args.dry_run:
            for event in actionable:
                print(json.dumps(event.payload(), ensure_ascii=False), flush=True)
    if args.twice:
        again, failed = collect(sources)
        failures.update(failed)
        for key in results.keys() & again.keys():
            if {e.id for e in results[key]} != {e.id for e in again[key]}:
                failures[key] = "IDs changed between fetches"
                print(f"ERROR {key}: unstable ID set", flush=True)
        print("Second-fetch stability check: " + ("FAILED" if failures else "passed"), flush=True)
    if args.dry_run:
        return int(bool(failures))
    from .notify import send_email
    with connect(ROOT / "events.db") as db:
        for key, events in results.items():
            observe(db, key, events, now)
        sent = deliver(db, now, set(results), send_email)
        report_health(db, {s.key: s.key in results for s in sources}, send_email)
        print(f"Delivered {sent} recruiting event/announcement updates", flush=True)
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
