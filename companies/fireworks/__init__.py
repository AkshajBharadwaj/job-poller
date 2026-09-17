"""US SWE/ML internships on Fireworks AI's official hiring board."""

from ..feeds import ashby_internships_us

COMPANY_NAME = "Fireworks AI"
CAREERS_URL = "https://jobs.ashbyhq.com/fireworks"


def fetch_jobs() -> list[dict]:
    return ashby_internships_us("fireworks")
