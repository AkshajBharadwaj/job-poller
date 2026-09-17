"""US SWE/ML internships on Luma AI's official hiring board."""

from ..feeds import ashby_internships_us

COMPANY_NAME = "Luma AI"
CAREERS_URL = "https://jobs.ashbyhq.com/lumaai"


def fetch_jobs() -> list[dict]:
    return ashby_internships_us("lumaai")
