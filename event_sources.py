"""Public recruiting feeds. Fetching is read-only; no mail or database writes.

Keep these separate from company job adapters and their internship filters.
Sources without a public calendar are explicitly announcement watches, not
complete event feeds. Never infer registration availability from generic copy.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

from bs4 import BeautifulSoup

from . import http


def clean(value):
    return " ".join(BeautifulSoup(str(value or ""), "html.parser").get_text(" ").split())


def canonical(url):
    p = urlsplit(url)
    if p.scheme not in ("https", "http") or not p.netloc:
        raise ValueError("Expected a public HTTP(S) URL")
    query = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")]
    return urlunsplit((p.scheme, p.netloc.lower(), p.path.rstrip("/"), urlencode(sorted(query)), ""))


def timestamp(value):
    if not value:
        return None
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


@dataclass(frozen=True)
class Event:
    id: str
    company: str
    title: str
    url: str
    when: str = "Not published — check source"
    location: str = "Not published — check source"
    eligibility: str = "Check source for eligibility and restrictions"
    deadline: str = ""
    start: str = ""
    status: str = "listed"
    details: str = ""
    kind: str = "event"
    cost: str = "Not stated — check source"

    def actionable(self, now):
        if self.kind == "announcement":
            return True
        if self.status not in ("listed", "open", "waitlist"):
            return False
        if self.deadline and timestamp(self.deadline) <= now:
            return False
        if self.start and self.start[:10] < now.date().isoformat():
            return False
        return bool(self.start or self.deadline)

    def payload(self):
        return asdict(self)


@dataclass(frozen=True)
class Source:
    key: str
    company: str
    url: str
    parser: str


JANE = "https://www.janestreet.com"
SOURCES = tuple(
    Source("jane-" + region, "Jane Street", JANE + "/jobs/" + file, "jane_events")
    for region, file in (
        ("main", "events.json"), ("nyc", "events-from-gsheet-nyc.json"),
        ("ldn", "events-from-gsheet-ldn.json"), ("hkg", "events-from-gsheet-hkg.json"),
    )
) + (
    Source("jane-programs", "Jane Street", JANE + "/jobs/programs-endpoint.json", "jane_programs"),
    Source("optiver", "Optiver", "https://www.optiver.com/join-us/events/", "optiver"),
    Source("figma", "Figma", "https://www.figma.com/careers/early-career/", "announcement"),
    Source("databricks", "Databricks", "https://www.databricks.com/company/careers/university-recruiting", "announcement"),
)


def parse_jane_events(data):
    if not isinstance(data, list):
        raise ValueError("Jane Street event feed is no longer a list")
    result = []
    for row in data:
        # Generic conference sponsorship is not a recruiting signup opportunity.
        if "conference" in row["event_type"].lower() or not row.get("event_url"):
            continue
        url = canonical(row["event_url"])
        result.append(Event(
            id=url, company="Jane Street", title=clean(row["position"]), url=url,
            start=row["event_date"], when=clean(row["event_date"] + " " + row.get("event_time", "")),
            location=clean(row.get("event_location")),
            deadline=row.get("event_registration_deadline") or "",
            details=clean(row.get("event_description")),
        ))
    return result


def parse_jane_programs(data):
    if not isinstance(data, list):
        raise ValueError("Jane Street program feed is no longer a list")
    result = []
    for program in data:
        # Scholarships and faculty research positions are not recruiting events.
        if re.search(r"fellowship|visiting researcher", program["name"], re.I):
            continue
        for row in program["sessions"]:
            if not row.get("apply_page") or not row.get("deadline"):
                continue
            url = canonical(urljoin(JANE, row["apply_page"]))
            result.append(Event(
                id=url, company="Jane Street", title=program["name"] + " — " + row["office"],
                url=url, when=clean(row["dates"]), deadline=row["deadline"], status="open",
                location="Virtual" if row.get("designate_as_virtual") else row["office"],
                eligibility=clean(row.get("custom_text") or ", ".join(program.get("category_filter", [])))
                or "Check source for eligibility and restrictions",
                details=clean(row.get("additional_info")),
            ))
    return result


def parse_optiver(html, base):
    # Embedded props drive the actual event listing, including the closed flag.
    match = re.search(r"React\.createElement\(Components\.EventsList,\s*(\{)", html)
    if not match:
        raise ValueError("Optiver EventsList props missing; parser needs review")
    props, _ = json.JSONDecoder().raw_decode(html[match.start(1):])
    result = []
    for row in props["items"]:
        url = canonical(urljoin(base, row["href"]))
        result.append(Event(
            id=url, company="Optiver", title=clean(row["title"]), url=url,
            start=row["dateTimeIso"], when=clean(row["dateTime"]) + " (listing time; confirm timezone on source)",
            location=clean(row["location"]), eligibility=clean(row["tag"]),
            details=clean(row.get("description")), status="closed" if row["closed"] else "listed",
        ))
    return result


def parse_announcement(html, source):
    """Watch only recruiting-event blocks, never whole-page CSS/nav/job changes.

    First snapshot is a silent baseline. Later changes are clearly labeled
    unverified announcements, not invented event dates or registration claims.
    """
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main") or soup.find(id="main")
    if main is None:
        raise ValueError("Main content missing; cannot safely watch announcements")
    for node in main.select("script, style, nav, footer"):
        node.decompose()
    if not re.search(r"early career|university|students|intern", main.get_text(" "), re.I):
        raise ValueError("Recruiting page content missing")
    blocks = []
    for heading in main.find_all(re.compile(r"^h[1-6]$")):
        title = heading.get_text(" ", strip=True)
        if not re.search(r"figfest|brickfest|recruiting events|campus events|upcoming events", title, re.I):
            continue
        # Bounded content until next heading. Exclude images, scripts and layout.
        parts = [title]
        for node in heading.next_elements:
            if getattr(node, "name", None) and re.fullmatch(r"h[1-6]", node.name):
                break
            if getattr(node, "name", None) == "a" and node.get("href"):
                link = urljoin(source.url, node["href"])
                if link.startswith(("http://", "https://")):
                    parts.append(link)
            if isinstance(node, str) and node.parent.name not in ("script", "style"):
                parts.append(str(node))
        blocks.append(" ".join(" ".join(parts).split()))
    return [Event(id=canonical(source.url), company=source.company,
                  title=source.company + " recruiting-event announcement changed", url=source.url,
                  kind="announcement", status="unverified",
                  details="\n".join(sorted(set(blocks))) or "No public recruiting-event section found.")]


def fetch(source):
    with http.session(retries=1) as session:
        response = session.get(source.url)
        response.raise_for_status()
        if source.parser == "jane_events":
            events = parse_jane_events(response.json())
        elif source.parser == "jane_programs":
            events = parse_jane_programs(response.json())
        elif source.parser == "optiver":
            events = parse_optiver(response.text, source.url)
        elif source.parser == "announcement":
            events = parse_announcement(response.text, source)
        else:
            raise ValueError("Unknown source parser")
    for event in events:
        if not event.id or not event.title:
            raise ValueError("Event missing stable ID or title")
        canonical(event.url)
        if event.start:
            timestamp(event.start)
        if event.deadline:
            timestamp(event.deadline)
    return events
