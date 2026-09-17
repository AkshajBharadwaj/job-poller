# Job Poller — personal deployment

Polls career sites for US SWE/ML internships and emails newly discovered
matches. The current deployment includes 355 company adapters.


## Production

- DigitalOcean Ubuntu VM; code at `/opt/careers`, runtime user `jobpoller`.
- Run from `/opt`: `/opt/careers/.venv/bin/python -m careers.watch`.
- `job-poller.timer` runs five minutes after the previous run completes.
  Full runs may take several minutes; this is not a five-minute detection SLA.
- Gmail API, send-only OAuth, email only. See [GMAIL_SETUP.md](GMAIL_SETUP.md).
- Secrets, `jobs.db`, logs and virtualenv stay on the machines, never in Git.
- The first successful poll for each company seeds existing jobs without
  emailing them. See [AI_QUANT_COVERAGE.md](AI_QUANT_COVERAGE.md) for current
  opportunities and coverage gaps.

For initial installation, use `systemd/job-poller-digitalocean.service` as
`/etc/systemd/system/job-poller.service` and the existing timer file. Do not
replace a running deployment's `.env` or database during code updates.

## Local authorization

Install `requirements-gmail-setup.txt` into the local virtualenv, then:

```sh
.venv/bin/python -I authorize_gmail.py --sender YOUR_EMAIL --recipient YOUR_EMAIL
```

The `-I` is important: the repository's `http.py` otherwise shadows Python's
standard-library package when invoking the script directly. Complete the
browser flow while the terminal remains running. Never commit or share the
generated `.env` or downloaded OAuth client JSON.

## Development

Read [AGENTS.md](AGENTS.md) and [companies/README.md](companies/README.md).
Run `python -m careers.check COMPANY --twice` from the package's parent for
read-only validation, not `careers.watch`. Adapters are auto-discovered.

Known limitations: some sites block VM traffic; a company adapter existing
does not guarantee its feed is healthy. The current notification path marks
jobs seen before delivery, so a failed email is not automatically retried.
