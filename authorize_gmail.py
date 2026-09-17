"""Authorize Gmail locally, then write private email-only settings to .env.

Run with the setup dependencies from requirements-gmail-setup.txt installed.
Only gmail.send is requested; this does not send a message.
"""

import argparse
import os
from pathlib import Path

from dotenv import set_key
from google_auth_oauthlib.flow import InstalledAppFlow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sender", required=True)
    parser.add_argument("--recipient", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    client = root / "gmail-client.json"
    client.chmod(0o600)
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client), scopes=["https://www.googleapis.com/auth/gmail.send"]
    )
    credentials = flow.run_local_server(
        host="127.0.0.1", port=0, open_browser=False,
        timeout_seconds=600, prompt="consent", login_hint=args.sender,
        success_message="Gmail authorization complete. You may close this tab.",
    )
    if not credentials.refresh_token:
        raise RuntimeError("Google did not return an offline refresh token")
    env = root / ".env"
    descriptor = os.open(env, os.O_CREAT | os.O_WRONLY, 0o600)
    os.close(descriptor)
    env.chmod(0o600)
    values = {
        "SMS_ALERTS_ENABLED": "false",
        "EMAIL_PROVIDER": "gmail_api",
        "EMAIL_FROM": args.sender,
        "EMAIL_TO": args.recipient,
        "GMAIL_CLIENT_ID": credentials.client_id,
        "GMAIL_CLIENT_SECRET": credentials.client_secret,
        "GMAIL_REFRESH_TOKEN": credentials.refresh_token,
    }
    for key, value in values.items():
        set_key(str(env), key, value)
    env.chmod(0o600)
    print("Authorization saved to .env (permissions 0600). No email sent.")


if __name__ == "__main__":
    main()
