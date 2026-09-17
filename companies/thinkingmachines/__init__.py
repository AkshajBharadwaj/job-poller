"""US SWE/ML internships on Thinking Machines Lab's official hiring board."""

from ..feeds import ashby_internships_us

COMPANY_NAME = "Thinking Machines Lab"
CAREERS_URL = "https://jobs.ashbyhq.com/thinkingmachines"


def fetch_jobs() -> list[dict]:
    return ashby_internships_us("thinkingmachines")
