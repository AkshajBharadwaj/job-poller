from ..quant_boards import quant_greenhouse_internships

COMPANY_NAME = "Da Vinci Trading"
CAREERS_URL = "https://job-boards.greenhouse.io/davinciderivatives"


def fetch_jobs() -> list[dict]:
    return quant_greenhouse_internships("davinciderivatives")
