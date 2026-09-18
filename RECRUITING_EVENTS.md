# Recruiting-event alerts

Separate from job polling: `python -m careers.event_watch` from `/opt` on
the VM. Install `requirements-events.txt`. Uses the existing Gmail sender,
with no extra Gmail permissions, paid APIs, SMS, or automatic signups.

## Enabled sources

- Jane Street: official public event JSON feeds (main, NYC, London, Hong Kong)
  and program sessions. Includes dated signup links, campus networking,
  interview prep and recruiting tech talks. Excludes conference sponsorship
  listings, entries with no signup/details link, research positions and fellowships.
- Optiver: official recruiting-events listing, with explicit closed flags.
  All regions and career stages, including virtual events when listed.
- Figma: early-career recruiting-events / FigFest announcement sections.
- Databricks: university-recruiting page, watching for recruiting-event /
  BrickFest sections appearing or changing.

The last two are **announcement watches**, not complete calendars. Their first
snapshot is silent, then substantive section changes generate explicitly
unverified page-update alerts. Currently no public signup is exposed there.
Private invitations, campus-login-only calendars, LinkedIn posts and arbitrary
Luma pages are not covered. Citadel returned 403 from the VM and is not enabled.
General product webinars/customer conferences are not monitored. This is initial
coverage, not an all-company event search. New verified feeds belong in
`event_sources.py`, not the job-adapter auto-discovery package.

## Delivery and operations

`event-poller.timer` checks 30 minutes after each completed run. Initial upcoming
events are emailed as a digest (up to 25 per email), not silently marked seen.
Subsequent alerts cover new listings, changed time/location/deadline, and observed
reopenings. Availability is only labeled confirmed open when the source provides
an application deadline; linked forms can still close early. Follow the source
for eligibility, costs and timezone. Missing fields are never invented.

State is separate in `events.db`. Unsent deliveries persist; successful sends
are marked sent afterwards. Failed sources defer their pending mail, and expired
or removed listings aren't sent. A source failing three consecutive polls sends
one health alert, then a recovery email when fixed. Source failures don't stop
other sources. A lock prevents overlapping live runs.

Delivery is **at least once**, not exactly once: if Gmail accepts mail but the
connection dies before confirmation, a later retry may duplicate that digest.
Normal successful runs deduplicate. Do not delete `events.db` to retry mail:
that would resend the initial digest. Back it up alongside `jobs.db`.

```sh
cd /opt
/opt/careers/.venv/bin/python -m unittest careers.tests.test_event_polling
/opt/careers/.venv/bin/python -m careers.event_watch --dry-run --twice
sudo systemctl enable --now event-poller.timer
sudo systemctl start event-poller.service
sudo journalctl -u event-poller.service -n 60 --no-pager
sudo systemctl disable --now event-poller.timer  # pause future runs
```

Dry runs send nothing and do not create or mutate the event database.
`--source` can restrict diagnostics to one or more source keys; use `--dry-run`
when diagnosing. The existing job timer, adapters and database are unchanged.
