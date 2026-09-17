"""US SWE/ML internships on Poolside's official hiring board."""

from ..feeds import ashby_internships_us

COMPANY_NAME = "Poolside"
CAREERS_URL = "https://jobs.ashbyhq.com/poolside"


def fetch_jobs() -> list[dict]:
    return ashby_internships_us("poolside")
