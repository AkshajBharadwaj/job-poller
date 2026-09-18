# Career and community-event alerts

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

## UW Seattle and Bay Area community coverage

Community sources intentionally broaden the recruiting-only scope to technical
talks, developer/AI nights, hackathons, startup networking and student clubs.
They run on the same 30-minute timer and email account, not the job timer.

- **University of Washington (Seattle):** Allen School's public Trumba calendar,
  plus the public Google calendar linked on its undergraduate events page for
  student organizations and company events. Academic holidays, admissions,
  dissertation defenses and routine advising are excluded. Google recurrences
  and exceptions are expanded over the next 90 days. UW affiliation may be required.
- **Bay Area AI and tech:** public Luma SF discovery pages. These return a rolling
  initial window of up to 25 listings per category, **not every event on Luma**.
  Tech listings require a technical/startup/engineering signal. Out-of-region
  coordinates and explicitly closed registrations are excluded; waitlists are labeled.
- **SF Tech Week:** public iCalendar from [the curated Luma calendar](https://luma.com/sftw).
  This is not a complete mirror of the official a16z schedule. The official site
  returned HTTP 429 from the VM. The iCal feed advertises a 12-hour refresh interval,
  so polling every 30 minutes does not guarantee 30-minute source freshness.

Times are shown in Pacific time. Events which have already started are not new
community alerts. Shared Luma event IDs deduplicate across the three feeds.
Community digests use compact listings (up to 100 per email); recruiting digests
retain their detailed format (25 per email). No signups are submitted automatically.
Costs and host approval requirements are labeled where exposed, never guessed.

Direct organizer calendars can be added for earlier discovery. Private/invite-only
events, UW-login-only feeds and the user's personal invitations are not accessible.
The GPT-6 community night organizer has not been identified or directly monitored.

Figma and Databricks are **announcement watches**, not complete calendars. Their first
snapshot is silent, then substantive section changes generate explicitly
unverified page-update alerts. Currently no public signup is exposed there.
Private invitations, campus-login-only calendars, LinkedIn posts and arbitrary
Luma pages are not covered. Citadel returned 403 from the VM and is not enabled.
General product webinar calendars are not monitored. This is initial
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
/opt/careers/.venv/bin/python -m unittest careers.tests.test_community_events
/opt/careers/.venv/bin/python -m careers.event_watch --dry-run --twice
sudo systemctl enable --now event-poller.timer
sudo systemctl start event-poller.service
sudo journalctl -u event-poller.service -n 60 --no-pager
sudo systemctl disable --now event-poller.timer  # pause future runs
```

Dry runs send nothing and do not create or mutate the event database.
`--source` can restrict diagnostics to one or more source keys; use `--dry-run`
when diagnosing. The existing job timer, adapters and database are unchanged.
