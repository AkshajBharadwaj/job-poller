"""US SWE/ML internships on Reflection AI's official hiring board."""

from ..feeds import ashby_internships_us

COMPANY_NAME = "Reflection AI"
CAREERS_URL = "https://jobs.ashbyhq.com/reflectionai"


def fetch_jobs() -> list[dict]:
    return ashby_internships_us("reflectionai")
