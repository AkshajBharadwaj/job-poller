"""US SWE/ML internships on Factory's official hiring board."""

from ..feeds import ashby_internships_us

COMPANY_NAME = "Factory"
CAREERS_URL = "https://jobs.ashbyhq.com/factory"


def fetch_jobs() -> list[dict]:
    return ashby_internships_us("factory")
