"""Prime Intellect's technical internship, including its generic title."""

from ..feeds import ashby_jobs
from ...filters import is_swe_ml_title, is_internship_title, is_us_job

COMPANY_NAME = "Prime Intellect"
CAREERS_URL = "https://jobs.ashbyhq.com/PrimeIntellect"


def fetch_jobs() -> list[dict]:
    # The official 'Internship' description explicitly covers AI, systems,
    # distributed compute and cryptography (verified 2026-09-17). Do not
    # admit unrelated growth/marketing internships from this same board.
    # This internship is incorrectly tagged FullTime in Ashby's feed, so
    # use the explicit title rather than the structured employment filter.
    jobs = ashby_jobs("PrimeIntellect")
    for job in jobs:
        job["locations"] = ["San Francisco, CA" if loc == "San Francisco" else loc
                            for loc in job["locations"]]
    return [job for job in jobs if is_us_job(job)
            and is_internship_title(job["title"])
            and (job["title"].strip() == "Internship" or is_swe_ml_title(job["title"]))]
