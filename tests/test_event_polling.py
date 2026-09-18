"""Offline tests: python -m unittest careers.tests.test_event_polling."""
from dataclasses import replace
from datetime import datetime, timezone
import json
import unittest

from ..event_sources import (Event, Source, canonical, parse_jane_events,
                             parse_jane_programs, parse_optiver, parse_announcement)
from ..event_watch import connect, observe, deliver, report_health

NOW = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)


class EventTests(unittest.TestCase):
    def setUp(self):
        self.db = connect(":memory:")
        self.event = Event("https://example.com/event", "Example", "Recruiting info session",
                           "https://example.com/event", start="2026-10-01", when="October 1")
        self.mail = []

    def tearDown(self):
        self.db.close()

    def send(self):
        return deliver(self.db, NOW, {"test"}, lambda *args: self.mail.append(args))

    def observe(self, event=None):
        observe(self.db, "test", [event or self.event], NOW)

    def test_initial_digest_and_dedup(self):
        self.observe()
        self.assertEqual(self.send(), 1)
        self.observe()
        self.assertEqual(self.send(), 0)
        self.assertEqual(len(self.mail), 1)

    def test_failed_delivery_retries(self):
        self.observe()
        def fail(*args):
            raise RuntimeError("mail unavailable")
        with self.assertRaises(RuntimeError):
            deliver(self.db, NOW, {"test"}, fail)
        self.assertEqual(self.db.execute("SELECT state,attempts FROM deliveries").fetchone(), ("pending", 1))
        self.assertEqual(self.send(), 1)

    def test_closed_then_reopened(self):
        self.observe()
        self.send()
        self.observe(replace(self.event, status="closed"))
        self.assertEqual(self.send(), 0)
        self.observe()
        self.assertEqual(self.send(), 1)

    def test_expired_and_closed_excluded(self):
        for event in (replace(self.event, start="2025-10-01"),
                      replace(self.event, deadline="2026-09-18T11:59:00Z"),
                      replace(self.event, status="closed"), replace(self.event, start="")):
            self.assertFalse(event.actionable(NOW))

    def test_announcement_baseline_and_changes(self):
        event = replace(self.event, kind="announcement", details="No signup", status="unverified")
        self.observe(event)
        self.assertEqual(self.send(), 0)
        self.observe(replace(event, details="New signup information"))
        self.assertEqual(self.send(), 1)
        self.assertIn("NOT verified", self.mail[0][1])

    def test_cosmetic_event_change_no_alert(self):
        self.observe()
        self.send()
        self.observe(replace(self.event, details="Different wording", title="Same session"))
        self.assertEqual(self.send(), 0)

    def test_reschedule_supersedes_unsent(self):
        self.observe()
        self.observe(replace(self.event, when="October 2", start="2026-10-02"))
        self.assertEqual(self.send(), 1)
        self.assertIn("October 2", self.mail[0][1])

    def test_failed_source_defers_delivery(self):
        self.observe()
        self.assertEqual(deliver(self.db, NOW, set(), lambda *a: self.fail("should not send")), 0)
        self.assertEqual(self.send(), 1)

    def test_community_source_fallback_does_not_repeat(self):
        event = replace(self.event, kind="community", start="2026-10-01T12:00:00Z")
        self.observe(event)
        self.send()
        observe(self.db, "fallback", [replace(event, start="2026-10-01T12:00:00+00:00", location="See source")], NOW)
        self.assertEqual(deliver(self.db, NOW, {"fallback"}, lambda *a: self.fail("Duplicate")), 0)

    def test_disappearance_cancels_stale_delivery(self):
        self.observe()
        observe(self.db, "test", [], NOW)
        self.assertEqual(self.send(), 0)
        self.observe()
        self.assertEqual(self.send(), 1)
        observe(self.db, "test", [], NOW)
        self.observe()
        self.assertEqual(self.send(), 0)

    def test_health_alert_once_then_recovery(self):
        sender = lambda *args: self.mail.append(args)
        for _ in range(4):
            report_health(self.db, {"test": False}, sender)
        self.assertEqual(len(self.mail), 1)
        report_health(self.db, {"test": True}, sender)
        self.assertEqual(len(self.mail), 2)

    def test_canonical_urls(self):
        self.assertEqual(canonical("https://EXAMPLE.com/a/?utm_source=x&id=3#b"), "https://example.com/a?id=3")
        with self.assertRaises(ValueError):
            canonical("javascript:bad")

    def test_jane_no_signup_and_conferences_excluded(self):
        row = dict(event_type="Info Session", event_url="https://example.com/register",
                   position="Meet &amp; greet", event_date="2026-10-01", event_location="Virtual")
        events = parse_jane_events([row, dict(row, event_url=None), dict(row, event_type="Conference")])
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].title, "Meet & greet")
        self.assertEqual(events[0].location, "Virtual")

    def test_program_deadline(self):
        data = [{"name": "FOCUS", "sessions": [{"apply_page": "/apply-focus", "office": "NYC",
                 "dates": "October 2026", "deadline": "2026-10-01T00:00:00Z"}]}]
        self.assertTrue(parse_jane_programs(data)[0].actionable(NOW))
        data[0]["sessions"][0]["deadline"] = "2026-01-01T00:00:00Z"
        self.assertFalse(parse_jane_programs(data)[0].actionable(NOW))

    def test_optiver_props(self):
        props = {"items": [{"href": "/event/123", "title": "Campus session", "dateTimeIso": "2026-10-01T13:00",
                           "dateTime": "October 1, 1pm", "location": "Virtual", "tag": "Students", "closed": False}]}
        html = "React.createElement(Components.EventsList," + json.dumps(props) + ")"
        self.assertEqual(parse_optiver(html, "https://example.com")[0].id, "https://example.com/event/123")
        with self.assertRaises(ValueError):
            parse_optiver("Site changed", "https://example.com")

    def test_announcement_ignores_nav_jobs_and_scripts(self):
        source = Source("figma", "Figma", "https://example.com", "announcement")
        html = '<main><h1>Early career</h1><h3>FigFest</h3><p>Info <a href="/signup">Register</a></p><h2>Jobs</h2><p>Engineer</p></main>'
        event = parse_announcement(html, source)[0]
        self.assertIn("https://example.com/signup", event.details)
        self.assertNotIn("Engineer", event.details)
        self.assertEqual(event, parse_announcement(html.replace("Engineer", "Designer"), source)[0])
        with self.assertRaises(ValueError):
            parse_announcement("<html>blocked</html>", source)


if __name__ == "__main__":
    unittest.main()
