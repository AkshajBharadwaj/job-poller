from ..quant_boards import quant_greenhouse_internships

COMPANY_NAME = "Aquatic Capital Management"
CAREERS_URL = "https://job-boards.greenhouse.io/aquaticcapitalmanagement"


def fetch_jobs() -> list[dict]:
    return quant_greenhouse_internships("aquaticcapitalmanagement")
