"""US SWE/ML internships on World Labs's official hiring board."""

from ..feeds import ashby_internships_us

COMPANY_NAME = "World Labs"
CAREERS_URL = "https://jobs.ashbyhq.com/worldlabs"


def fetch_jobs() -> list[dict]:
    return ashby_internships_us("worldlabs")
