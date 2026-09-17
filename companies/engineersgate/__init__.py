from ..quant_boards import quant_greenhouse_internships

COMPANY_NAME = "Engineers Gate"
CAREERS_URL = "https://job-boards.greenhouse.io/engineersgate"


def fetch_jobs() -> list[dict]:
    return quant_greenhouse_internships("engineersgate")
