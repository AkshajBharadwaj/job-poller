"""Opt-in normalization for quant boards using bare office-city labels.

Used only by adapters whose official boards list these US offices. This
does not change any existing company's filtering or the global poller.
"""

import re

from .feeds import greenhouse_jobs
from ..filters import internships_in_us


def quant_greenhouse_internships(board: str) -> list[dict]:
    # Explicit office labels, not substring matches (e.g. London stays UK).
    offices = {"Chicago": "Chicago, IL", "New York": "New York, NY",
               "Miami": "Miami, FL"}
    jobs = greenhouse_jobs(board)
    for job in jobs:
        job["locations"] = [
            offices.get(part.strip(), part.strip())
            for location in job["locations"]
            for part in re.split(r"[;|]", location) if part.strip()
        ]
    return internships_in_us(jobs)
