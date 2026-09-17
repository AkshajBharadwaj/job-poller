from ..quant_boards import quant_greenhouse_internships

COMPANY_NAME = "Headlands Technologies"
CAREERS_URL = "https://job-boards.greenhouse.io/headlandstechnologiesllc"


def fetch_jobs() -> list[dict]:
    return quant_greenhouse_internships("headlandstechnologiesllc")
