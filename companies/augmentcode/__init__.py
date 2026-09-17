from ..feeds import greenhouse_internships_us

COMPANY_NAME = "Augment Code"
CAREERS_URL = "https://www.augmentcode.com/careers"


def fetch_jobs() -> list[dict]:
    return greenhouse_internships_us("augmentcomputing")
