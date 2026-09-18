"""UW Seattle and Bay Area community events, separate from recruiting filters."""
from datetime import datetime, time, timedelta, timezone
import json
import re
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from icalendar import Calendar
import recurring_ical_events

from .event_sources import Event, canonical, clean, timestamp

PACIFIC = ZoneInfo("America/Los_Angeles")
BAY = "Bay Area tech community"


def when(start):
    return timestamp(start).astimezone(PACIFIC).strftime("%a %b %d, %Y, %I:%M %p %Z")


def in_bay(coordinate):
    return (36.8 <= float(coordinate["latitude"]) <= 38.8 and
            -123.1 <= float(coordinate["longitude"]) <= -121.2)


def parse_uw(data):
    if not isinstance(data, list):
        raise ValueError("UW calendar schema changed")
    result = []
    for row in data:
        title = clean(row["title"])
        # Academic term dates and admissions sessions are not community/career events.
        if "Academic Calendar" in row.get("categoryCalendar", ""):
            continue
        if re.search(r"dissertation defense|ph\.?d\.? information|professional master|prospective student|admission", title, re.I):
            continue
        fields = {f["label"]: clean(f["value"]) for f in row.get("customFields", [])}
        topic = title + " " + fields.get("Event Types", "")
        if not re.search(r"career|recruit|employer|network|hack|workshop|talk|lecture|colloqui|seminar|webinar|kickoff|community|tech|\bAI\b|information session", topic, re.I):
            continue
        start = row["startDateTime"]
        if datetime.fromisoformat(start).tzinfo is None:
            start += row["startTimeZoneOffset"]
        status = "listed"
        if row.get("canceled"):
            status = "closed"
        elif row.get("reservationFull"):
            status = "waitlist" if row.get("waitingListAvailable") else "closed"
        elif row.get("openSignUp") and row.get("pastDeadline"):
            status = "closed"
        result.append(Event(
            id="uw-trumba:" + str(row["eventID"]), company="University of Washington",
            title=title, url=canonical(row["permaLinkUrl"]), start=start, when=when(start),
            location=clean(row.get("location")) or "UW Seattle — see source",
            eligibility=fields.get("Target Audience", "UW/public access varies; check event page"),
            details=clean(row.get("description"))[:1800], status=status, kind="community",
            cost="Payment required; check source" if row.get("requiresPayment") else "Not stated — check source",
        ))
    return result


def parse_luma_discovery(html):
    node = BeautifulSoup(html, "html.parser").select_one("script#__NEXT_DATA__")
    if node is None:
        raise ValueError("Luma page data missing")
    props = json.loads(node.string)["props"]["pageProps"]
    if props.get("place", {}).get("slug") != "sf":
        raise ValueError("Not the San Francisco discovery page")
    rows = props["initialEvents"]
    if not isinstance(rows, list):
        raise ValueError("Luma event schema changed")
    result = []
    for row in rows:
        event = row["event"]
        if event.get("visibility") != "public":
            continue
        coord = event.get("coordinate")
        virtual = event.get("location_type") == "online"
        if coord and not virtual and not in_bay(coord):
            continue
        availability = row.get("registration_availability")
        status = "listed"
        if row.get("waitlist_active") or availability == "waitlist":
            status = "waitlist"
        elif availability in ("closed", "sold-out", "sold_out", "ended"):
            status = "closed"
        info = row.get("ticket_info") or {}
        if info.get("is_sold_out") and status != "waitlist":
            status = "closed"
        place = event.get("geo_address_info") or {}
        hosts = ", ".join(h["name"] for h in (row.get("hosts") or []) if h.get("name"))
        if props.get("categoryPage", {}).get("category", {}).get("slug") == "tech":
            if not re.search(r"tech|\bAI\b|\bML\b|engineer|builder|founder|startup|hack|cod|developer|data|robot|\bYC\b|waymo|openai|anthropic|claude|google|microsoft|meta|figma|databricks|\bSRE\b|ruby|python|lean", event["name"] + " " + hosts, re.I):
                continue
        result.append(Event(
            id=event["api_id"], company=BAY, title=clean(event["name"]),
            url="https://luma.com/event/" + event["api_id"],
            start=event["start_at"], when=when(event["start_at"]),
            location="Virtual" if virtual else (place.get("city_state") or place.get("city") or "Bay Area — see source"),
            status=status, kind="community",
            eligibility="Host approval required; check eligibility" if info.get("require_approval") else "Check host's eligibility and registration requirements",
            cost="Free (as listed)" if info.get("is_free") else "Paid or price unconfirmed — see source",
            details=f"Hosts: {hosts or 'See event page'}. Public Luma discovery listing; not necessarily company-hosted or recruiting.",
        ))
    return result


def parse_luma_ics(text):
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("Expected public iCalendar feed")
    result = []
    for row in Calendar.from_ical(text).walk("VEVENT"):
        # Public calendar exports include past editions: actionable() filters time.
        uid = str(row["UID"]).split("@")[0]
        if not uid.startswith("evt-"):
            raise ValueError("Unexpected Luma UID")
        if row.get("RRULE"):
            raise ValueError("Recurring feed requires occurrence expansion")
        start = row.decoded("DTSTART")
        all_day = not isinstance(start, datetime)
        if all_day:
            start = datetime.combine(start, time.min, PACIFIC)
        elif start.tzinfo is None:
            raise ValueError("Expected timezone-aware Luma start")
        if row.get("GEO"):
            lat, lon = row["GEO"].latitude, row["GEO"].longitude
            if not in_bay({"latitude": lat, "longitude": lon}):
                continue
        location = str(row.get("LOCATION", ""))
        if location.startswith("http"):
            location = "Location shared on signup page"
        result.append(Event(
            id=uid, company=BAY, title=clean(row["SUMMARY"]),
            url="https://luma.com/event/" + uid, start=start.isoformat(),
            when=(start.date().isoformat() + " (all day)") if all_day else when(start.isoformat()),
            location=location or "Bay Area — see source", kind="community",
            status="closed" if str(row.get("STATUS", "")).upper() == "CANCELLED" else "listed",
            details="SF Tech Week curated Luma calendar. " + str(row.get("DESCRIPTION", ""))[:1200],
        ))
    return result


def parse_uw_ics(text, now=None):
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("Expected UW public calendar")
    now = now or datetime.now(timezone.utc)
    # Expand RRULE/EXDATE/overrides using the standard iCalendar semantics.
    rows = recurring_ical_events.of(Calendar.from_ical(text)).between(now, now + timedelta(days=90))
    result = []
    for row in rows:
        title = clean(row.get("SUMMARY"))
        if re.search(r"advising|quick questions|office hours|community hours", title, re.I):
            continue
        start = row.decoded("DTSTART")
        if not isinstance(start, datetime):
            start = datetime.combine(start, time.min, PACIFIC)
        elif start.tzinfo is None:
            start = start.replace(tzinfo=PACIFIC)
        # Original recurrence ID stays stable even when an occurrence is moved.
        recurrence = row.get("RECURRENCE-ID")
        occurrence = str(recurrence.dt) if recurrence is not None else ""
        identity = "uw-gcal:" + str(row["UID"]) + ":" + occurrence
        description = clean(row.get("DESCRIPTION"))
        result.append(Event(
            id=identity, company="University of Washington", title=title,
            url=str(row.get("URL") or "https://www.cs.washington.edu/academics/undergraduate/student-services/undergraduate-events-calendar/"),
            start=start.isoformat(), when=when(start.isoformat()),
            location=clean(row.get("LOCATION")) or "UW Seattle — see source",
            status="closed" if str(row.get("STATUS", "")).upper() == "CANCELLED" else "listed",
            kind="community", eligibility="Primarily Allen School undergraduates; confirm event restrictions",
            details=description[:1800],
        ))
    return result


def parse_community(text, source):
    if source.parser == "uw_trumba":
        return parse_uw(json.loads(text))
    if source.parser == "luma_discovery":
        return parse_luma_discovery(text)
    if source.parser == "uw_ics":
        return parse_uw_ics(text)
    return parse_luma_ics(text)
