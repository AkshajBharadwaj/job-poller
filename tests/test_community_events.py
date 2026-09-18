from datetime import datetime, timezone
import json
import unittest
from unittest.mock import patch

from ..community_sources import parse_luma_discovery, parse_luma_ics, parse_uw, parse_uw_ics
from ..event_sources import SOURCES
from ..event_watch import collect

NOW = datetime(2026, 9, 18, 12, tzinfo=timezone.utc)


def calendar(event):
    return 'BEGIN:VCALENDAR\r\nVERSION:2.0\r\n' + event + '\r\nEND:VCALENDAR\r\n'


def vevent(extra='', uid='evt-test@events.lu.ma', start='20261001T180000Z'):
    return ('BEGIN:VEVENT\r\nUID:' + uid + '\r\nDTSTART:' + start +
            '\r\nDTEND:20261001T190000Z\r\nSUMMARY:AI community night\r\n' +
            extra + '\r\nEND:VEVENT')


class CommunityTests(unittest.TestCase):
    def luma(self, **changes):
        event = dict(api_id='evt-test', name='AI community night', visibility='public',
                     start_at='2026-10-01T18:00:00Z', coordinate={'latitude': 37.77, 'longitude': -122.4},
                     geo_address_info={'city_state': 'San Francisco, CA'})
        event.update(changes.pop('event', {}))
        row = dict(event=event, hosts=[{'name': None}], registration_availability='open',
                   ticket_info={'is_free': True})
        row.update(changes)
        props = {'place': {'slug': 'sf'}, 'initialEvents': [row]}
        return '<script id="__NEXT_DATA__" type="application/json">' + json.dumps({'props': {'pageProps': props}}) + '</script>'

    def test_discovery_fields_and_pacific_time(self):
        e = parse_luma_discovery(self.luma())[0]
        self.assertEqual(e.id, 'evt-test')
        self.assertIn('11:00 AM PDT', e.when)
        self.assertEqual(e.cost, 'Free (as listed)')

    def test_public_geography_and_closed(self):
        self.assertFalse(parse_luma_discovery(self.luma(event={'visibility': 'private'})))
        self.assertFalse(parse_luma_discovery(self.luma(event={'coordinate': {'latitude': 40.7, 'longitude': -74}})))
        e = parse_luma_discovery(self.luma(registration_availability='closed'))[0]
        self.assertFalse(e.actionable(NOW))

    def test_waitlist_not_sold_out(self):
        e = parse_luma_discovery(self.luma(waitlist_active=True, ticket_info={'is_sold_out': True}))[0]
        self.assertEqual(e.status, 'waitlist')
        self.assertTrue(e.actionable(NOW))

    def test_started_event_is_not_upcoming(self):
        e = parse_luma_discovery(self.luma(event={'start_at': '2026-09-18T11:00:00Z'}))[0]
        self.assertFalse(e.actionable(NOW))

    def test_ics_uid_deduplicates_discovery(self):
        e = parse_luma_ics(calendar(vevent('GEO:37.77;-122.4')))[0]
        other = parse_luma_discovery(self.luma())[0]
        self.assertEqual((e.company, e.id, e.url), (other.company, other.id, other.url))

    def test_ics_cancelled_old_and_bad_schema(self):
        self.assertFalse(parse_luma_ics(calendar(vevent('STATUS:CANCELLED')))[0].actionable(NOW))
        self.assertFalse(parse_luma_ics(calendar(vevent(start='20241001T180000Z')))[0].actionable(NOW))
        with self.assertRaises(ValueError):
            parse_luma_ics('<html>Blocked</html>')

    def test_ics_all_day_and_folded_text(self):
        text = calendar(vevent()).replace('DTSTART:20261001T180000Z', 'DTSTART;VALUE=DATE:20261001')
        text = text.replace('SUMMARY:AI community night', 'SUMMARY:AI community\r\n  night')
        self.assertIn('all day', parse_luma_ics(text)[0].when)
        self.assertEqual(parse_luma_ics(text)[0].title, 'AI community night')

    def test_uw_filters_and_timezone(self):
        row = dict(eventID=123, title='Company recruiting fair', startDateTime='2026-10-01T13:00:00',
                   startTimeZoneOffset='-0700', permaLinkUrl='https://example.com/?eventid=123',
                   customFields=[], categoryCalendar='Allen School')
        e = parse_uw([row])[0]
        self.assertIn('01:00 PM PDT', e.when)
        self.assertFalse(parse_uw([dict(row, categoryCalendar='UW Seattle Academic Calendar')]))
        self.assertFalse(parse_uw([dict(row, title='Professional Masters Information Session')]))

    def test_uw_google_recurrence_and_routine_filter(self):
        text = calendar(vevent('RRULE:FREQ=WEEKLY;COUNT=2', uid='uw-event@google.com'))
        events = parse_uw_ics(text, NOW)
        self.assertEqual(len(events), 2)
        self.assertNotEqual(events[0].id, events[1].id)
        self.assertEqual([e.id for e in events], [e.id for e in parse_uw_ics(text, NOW)])
        self.assertFalse(parse_uw_ics(text.replace('AI community night', 'Advising Quick Questions'), NOW))

    def test_collect_cross_source_dedup_is_deterministic(self):
        e = parse_luma_discovery(self.luma())[0]
        sources = [s for s in SOURCES if s.key in ('bay-ai', 'bay-tech')]
        with patch('careers.event_watch.fetch', return_value=[e]):
            results, failures = collect(sources)
        self.assertFalse(failures)
        self.assertEqual(len(results['bay-ai']), 1)
        self.assertEqual(results['bay-tech'], [])


if __name__ == '__main__':
    unittest.main()
