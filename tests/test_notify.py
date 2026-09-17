import base64
import importlib
import unittest
from email import message_from_bytes
from unittest.mock import MagicMock, patch

notify = importlib.import_module(f"{__package__.rsplit('.', 1)[0]}.notify")


class NotificationTests(unittest.TestCase):
    def test_email_only_does_not_call_twilio(self):
        with patch.object(notify, "SMS_ALERTS_ENABLED", False), \
             patch.object(notify, "send_text") as sms, \
             patch.object(notify, "send_email") as email:
            notify.notify_new_job("Example", {
                "title": "Intern", "locations": ["US"], "url": "https://example.com"
            })
        sms.assert_not_called()
        email.assert_called_once()

    def test_gmail_refresh_and_encoded_message(self):
        session = MagicMock()
        session.post.return_value.json.return_value = {"access_token": "test-token"}
        with patch.multiple(notify, EMAIL_PROVIDER="gmail_api", EMAIL_FROM="sender@example.com",
                            EMAIL_TO="recipient@example.com", GMAIL_CLIENT_ID="client",
                            GMAIL_CLIENT_SECRET="secret", GMAIL_REFRESH_TOKEN="refresh"), \
             patch.object(notify.http, "session") as factory:
            factory.return_value.__enter__.return_value = session
            notify.send_email("New internship", "Job details")
        factory.assert_called_once_with(retries=0)
        self.assertEqual(session.post.call_count, 2)
        refresh, send = session.post.call_args_list
        self.assertEqual(refresh.kwargs["data"]["grant_type"], "refresh_token")
        self.assertEqual(send.kwargs["headers"]["Authorization"], "Bearer test-token")
        message = message_from_bytes(base64.urlsafe_b64decode(send.kwargs["json"]["raw"]))
        self.assertEqual(message["To"], "recipient@example.com")
        self.assertEqual(message["Subject"], "New internship")
        self.assertEqual(message.get_payload(decode=True).decode(), "Job details")

    def test_refresh_failure_does_not_send(self):
        session = MagicMock()
        session.post.return_value.raise_for_status.side_effect = RuntimeError("Unauthorized")
        with patch.multiple(notify, EMAIL_PROVIDER="gmail_api", EMAIL_FROM="sender@example.com",
                            EMAIL_TO="recipient@example.com", GMAIL_CLIENT_ID="client",
                            GMAIL_CLIENT_SECRET="secret", GMAIL_REFRESH_TOKEN="refresh"), \
             patch.object(notify.http, "session") as factory:
            factory.return_value.__enter__.return_value = session
            with self.assertRaises(RuntimeError):
                notify.send_email("Subject", "Body")
        self.assertEqual(session.post.call_count, 1)
