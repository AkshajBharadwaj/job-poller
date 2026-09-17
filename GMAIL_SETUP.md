# Gmail email-only deployment

The DigitalOcean deployment lives at `/opt/careers` on `138.68.4.253`.
The systemd timer is installed but disabled until authorization and delivery
have been tested. No previous database is available; the first production
poll establishes a baseline without sending existing postings.

DigitalOcean blocks SMTP. Use Gmail's HTTPS API with the `gmail.send` scope.
An existing Gmail account can be used; a dedicated sender is optional.

1. In Google Cloud Console, create or select a project and enable Gmail API.
2. Configure Google Auth Platform branding and audience for personal use.
3. Create a Desktop app OAuth client and download its client JSON securely.
4. Authorize the sender with an installed-app OAuth flow requesting only
   `https://www.googleapis.com/auth/gmail.send`, with offline access.
   Keep the resulting refresh token private, along with the client credentials.
5. For continuous operation, move the consent app out of Testing before the
   final authorization. Gmail refresh tokens issued in Testing expire after
   seven days. Follow Google's personal-use/verification guidance; do not
   request mailbox read or full-mail access.
6. Configure `/opt/careers/.env` with owner `jobpoller` and permissions `0600`:

   ```dotenv
   SMS_ALERTS_ENABLED=false
   EMAIL_PROVIDER=gmail_api
   EMAIL_FROM=YOUR_AUTHORIZED_GMAIL_ADDRESS
   EMAIL_TO=YOUR_RECIPIENT_ADDRESS
   GMAIL_CLIENT_ID=YOUR_CLIENT_ID
   GMAIL_CLIENT_SECRET=YOUR_CLIENT_SECRET
   GMAIL_REFRESH_TOKEN=YOUR_REFRESH_TOKEN
   ```

7. Send a user-approved test with `python -m careers.send_test_notification`
   using the VM virtualenv from `/opt`. Confirm inbox delivery before enabling
   `job-poller.timer`.

The existing poller records jobs before delivering notifications. Delivery
failures are not retried on the next poll; monitor service failures. The
Gmail API sender deliberately does not retry ambiguous send failures to avoid
duplicate messages.

References:
- https://developers.google.com/workspace/gmail/api/guides/sending
- https://developers.google.com/identity/protocols/oauth2/native-app
- https://developers.google.com/identity/protocols/oauth2/production-readiness/overview
