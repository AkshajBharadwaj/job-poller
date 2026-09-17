"""US SWE/ML internships on Cartesia's official hiring board."""

from ..feeds import ashby_internships_us

COMPANY_NAME = "Cartesia"
CAREERS_URL = "https://jobs.ashbyhq.com/cartesia"


def fetch_jobs() -> list[dict]:
    return ashby_internships_us("cartesia")
