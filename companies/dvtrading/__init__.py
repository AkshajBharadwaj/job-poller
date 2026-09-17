from ..quant_boards import quant_greenhouse_internships

COMPANY_NAME = "DV Trading"
CAREERS_URL = "https://job-boards.greenhouse.io/dvtrading"


def fetch_jobs() -> list[dict]:
    return quant_greenhouse_internships("dvtrading")
