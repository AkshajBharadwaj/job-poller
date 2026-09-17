"""US SWE/ML internships on Liquid AI's official hiring board."""

from ..feeds import ashby_internships_us

COMPANY_NAME = "Liquid AI"
CAREERS_URL = "https://jobs.ashbyhq.com/liquid-ai"


def fetch_jobs() -> list[dict]:
    return ashby_internships_us("liquid-ai")
