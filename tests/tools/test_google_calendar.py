import json
import unittest
from unittest.mock import MagicMock, patch

from agentor.tools.google_calendar import CalendarTool


def _mock_calendar_service():
    """Return a mocked Google Calendar service with default responses."""
    service = MagicMock()
    events = service.events.return_value

    # Default list response
    events.list.return_value.execute.return_value = {"items": []}

    # Default insert response
    events.insert.return_value.execute.return_value = {
        "id": "evt-1",
        "summary": "Test Event",
    }

    # Default delete response
    events.delete.return_value.execute.return_value = {}

    # Default get response (used by add_guests)
    events.get.return_value.execute.return_value = {
        "id": "evt-1",
        "attendees": [{"email": "existing@example.com"}],
    }

    # Default update response
    events.update.return_value.execute.return_value = {
        "id": "evt-1",
        "attendees": [
            {"email": "existing@example.com"},
            {"email": "new@example.com"},
        ],
    }
    return service


class TestGoogleCalendarTool(unittest.TestCase):
    @patch("agentor.tools.google_calendar.build")
    def test_init_requires_credentials(self, mock_build):
        """Ensure tool initialization fails when credentials are missing."""
        mock_build.return_value = _mock_calendar_service()
        with self.assertRaises(ValueError) as ctx:
            CalendarTool(credentials=None)
        self.assertIn("Credentials object is required", str(ctx.exception))

    @patch("agentor.tools.google_calendar.build")
    def test_list_events_success_with_timezone_aware_datetimes(self, mock_build):
        """Verify list_events works with timezone-aware datetime values."""
        service = _mock_calendar_service()
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "1"}]
        }
        mock_build.return_value = service

        tool = CalendarTool(credentials=object())
        result = tool.list_events(
            start_time="2026-03-27T00:00:00Z",
            end_time="2026-03-27T23:59:59Z",
        )
        parsed = json.loads(result)
        self.assertEqual(parsed, [{"id": "1"}])

        kwargs = service.events.return_value.list.call_args.kwargs
        self.assertEqual(kwargs["timeMin"], "2026-03-27T00:00:00Z")
        self.assertEqual(kwargs["timeMax"], "2026-03-27T23:59:59Z")

    @patch("agentor.tools.google_calendar.build")
    def test_list_events_rejects_naive_datetimes(self, mock_build):
        """Verify list_events rejects datetime values without timezone."""
        mock_build.return_value = _mock_calendar_service()

        tool = CalendarTool(credentials=object())
        result = tool.list_events(
            start_time="2026-03-27T00:00:00",
            end_time="2026-03-27T23:59:59",
        )

        self.assertIn("Datetime must include timezone", result)

    @patch("agentor.tools.google_calendar.build")
    def test_list_events_allows_higher_limit_for_internal_queries(self, mock_build):
        """Verify list_events supports higher limits used by free-slot scans."""
        service = _mock_calendar_service()
        mock_build.return_value = service

        tool = CalendarTool(credentials=object())
        tool.list_events(
            start_time="2026-03-27T00:00:00Z",
            end_time="2026-03-27T23:59:59Z",
            limit=250,
        )

        kwargs = service.events.return_value.list.call_args.kwargs
        self.assertEqual(kwargs["maxResults"], 250)

    @patch("agentor.tools.google_calendar.build")
    def test_list_events_error(self, mock_build):
        """Verify list_events returns an error string on API failures."""
        service = _mock_calendar_service()
        service.events.return_value.list.return_value.execute.side_effect = Exception(
            "API error"
        )
        mock_build.return_value = service

        tool = CalendarTool(credentials=object())
        result = tool.list_events(
            start_time="2026-03-27T00:00:00Z",
            end_time="2026-03-27T23:59:59Z",
        )
        self.assertIn("Error: API error", result)

    @patch("agentor.tools.google_calendar.build")
    def test_create_event_requires_title(self, mock_build):
        """Ensure create_event requires a non-empty title."""
        mock_build.return_value = _mock_calendar_service()
        tool = CalendarTool(credentials=object())

        result = tool.create_event(
            title="",
            start_time="2026-03-27T10:00:00Z",
            end_time="2026-03-27T11:00:00Z",
        )
        self.assertEqual(result, "Error: title is required.")

    @patch("agentor.tools.google_calendar.build")
    def test_create_event_success(self, mock_build):
        """Verify create_event builds payload and returns created event."""
        service = _mock_calendar_service()
        mock_build.return_value = service
        tool = CalendarTool(credentials=object())

        result = tool.create_event(
            title="Team Sync",
            start_time="2026-03-27T10:00:00Z",
            end_time="2026-03-27T11:00:00Z",
            location="Zoom",
        )
        parsed = json.loads(result)
        self.assertEqual(parsed["id"], "evt-1")

        kwargs = service.events.return_value.insert.call_args.kwargs
        self.assertEqual(kwargs["calendarId"], "primary")
        self.assertEqual(kwargs["body"]["summary"], "Team Sync")
        self.assertTrue(kwargs["body"]["start"]["dateTime"].endswith("Z"))
        self.assertTrue(kwargs["body"]["end"]["dateTime"].endswith("Z"))

    @patch("agentor.tools.google_calendar.build")
    def test_create_event_rejects_naive_datetimes(self, mock_build):
        """Verify create_event rejects datetime values without timezone."""
        mock_build.return_value = _mock_calendar_service()
        tool = CalendarTool(credentials=object())

        result = tool.create_event(
            title="Team Sync",
            start_time="2026-03-27T10:00:00",
            end_time="2026-03-27T11:00:00",
        )

        self.assertIn("Datetime must include timezone", result)

    @patch("agentor.tools.google_calendar.build")
    def test_find_free_slots_success(self, mock_build):
        """Verify free slot calculation returns at least one slot."""
        service = _mock_calendar_service()
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "start": {"dateTime": "2026-03-27T10:00:00Z"},
                    "end": {"dateTime": "2026-03-27T11:00:00Z"},
                }
            ]
        }
        mock_build.return_value = service
        tool = CalendarTool(credentials=object())

        result = tool.find_free_slots(
            start_time="2026-03-27T09:00:00Z",
            end_time="2026-03-27T12:00:00Z",
            meeting_minutes=30,
        )
        parsed = json.loads(result)
        self.assertIn("free_slots", parsed)
        self.assertGreaterEqual(len(parsed["free_slots"]), 1)

    @patch("agentor.tools.google_calendar.build")
    def test_find_free_slots_handles_all_day_events(self, mock_build):
        """Verify all-day events are treated as busy in free-slot search."""
        service = _mock_calendar_service()
        service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "start": {"date": "2026-03-27"},
                    "end": {"date": "2026-03-28"},
                }
            ]
        }
        mock_build.return_value = service
        tool = CalendarTool(credentials=object())

        result = tool.find_free_slots(
            start_time="2026-03-27T09:00:00Z",
            end_time="2026-03-27T12:00:00Z",
            meeting_minutes=30,
        )
        parsed = json.loads(result)
        self.assertEqual(parsed["free_slots"], [])

    @patch("agentor.tools.google_calendar.build")
    def test_delete_event_validation_and_success(self, mock_build):
        """Ensure delete_event validates input and deletes successfully."""
        service = _mock_calendar_service()
        mock_build.return_value = service
        tool = CalendarTool(credentials=object())

        self.assertEqual(tool.delete_event(event_id=""), "Error: event_id is required.")

        result = tool.delete_event(event_id="evt-1")
        parsed = json.loads(result)
        self.assertEqual(parsed["status"], "success")

        service.events.return_value.delete.assert_called_with(
            calendarId="primary",
            eventId="evt-1",
        )

    @patch("agentor.tools.google_calendar.build")
    def test_add_guests_validation(self, mock_build):
        """Ensure add_guests validates required arguments."""
        mock_build.return_value = _mock_calendar_service()
        tool = CalendarTool(credentials=object())

        self.assertEqual(
            tool.add_guests(event_id="", guest_emails=["a@example.com"]),
            "Error: event_id is required.",
        )
        self.assertIn(
            "guest_emails must be a non-empty list",
            tool.add_guests(event_id="evt-1", guest_emails=[]),
        )

    @patch("agentor.tools.google_calendar.build")
    def test_add_guests_success_and_dedup(self, mock_build):
        """Verify add_guests appends only new attendee emails."""
        service = _mock_calendar_service()
        mock_build.return_value = service
        tool = CalendarTool(credentials=object())

        result = tool.add_guests(
            event_id="evt-1",
            guest_emails=["existing@example.com", "new@example.com"],
            send_notifications=False,
        )
        parsed = json.loads(result)
        self.assertEqual(parsed["status"], "success")
        self.assertEqual(parsed["event_id"], "evt-1")
        self.assertEqual(parsed["message"], "Added 1 guest(s) to event.")

        update_kwargs = service.events.return_value.update.call_args.kwargs
        attendees = update_kwargs["body"]["attendees"]
        emails = sorted([a["email"] for a in attendees])

        self.assertEqual(
            emails,
            ["existing@example.com", "new@example.com"],
        )
        self.assertEqual(update_kwargs["sendUpdates"], "none")

    @patch("agentor.tools.google_calendar.build")
    def test_add_guests_dedup_duplicate_in_request(self, mock_build):
        """Verify duplicate emails in guest_emails list appear only once."""
        service = _mock_calendar_service()
        mock_build.return_value = service
        tool = CalendarTool(credentials=object())

        result = tool.add_guests(
            event_id="evt-1",
            guest_emails=["dup@example.com", "dup@example.com"],
            send_notifications=False,
        )
        parsed = json.loads(result)
        self.assertEqual(parsed["status"], "success")
        self.assertEqual(parsed["message"], "Added 1 guest(s) to event.")

    @patch("agentor.tools.google_calendar.build")
    def test_find_free_slots_validates_meeting_minutes(self, mock_build):
        """Verify find_free_slots rejects non-positive meeting_minutes."""
        mock_build.return_value = _mock_calendar_service()
        tool = CalendarTool(credentials=object())

        result = tool.find_free_slots(
            start_time="2026-03-27T09:00:00Z",
            end_time="2026-03-27T12:00:00Z",
            meeting_minutes=0,
        )
        self.assertIn("meeting_minutes must be greater than 0", result)

    @patch("agentor.tools.google_calendar.build")
    def test_find_free_slots_validates_time_order(self, mock_build):
        """Verify find_free_slots rejects when end_time <= start_time."""
        mock_build.return_value = _mock_calendar_service()
        tool = CalendarTool(credentials=object())

        result = tool.find_free_slots(
            start_time="2026-03-27T12:00:00Z",
            end_time="2026-03-27T09:00:00Z",
            meeting_minutes=30,
        )
        self.assertIn("end_time must be after start_time", result)

    @patch("agentor.tools.google_calendar.build")
    def test_capabilities_registered(self, mock_build):
        """Ensure all CalendarTool capabilities are exposed."""
        mock_build.return_value = _mock_calendar_service()
        tool = CalendarTool(credentials=object())

        fn_names = [fn.name for fn in tool.to_openai_function()]
        self.assertIn("list_events", fn_names)
        self.assertIn("create_event", fn_names)
        self.assertIn("find_free_slots", fn_names)
        self.assertIn("delete_event", fn_names)
        self.assertIn("add_guests", fn_names)


if __name__ == "__main__":
    unittest.main()
