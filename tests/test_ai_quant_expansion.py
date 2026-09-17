"""Focused, network-free regression tests for the additional target boards."""

import importlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != ROOT]
sys.path.insert(0, str(ROOT.parent))
quant = importlib.import_module(f"{ROOT.name}.companies.quant_boards")
prime = importlib.import_module(f"{ROOT.name}.companies.primeintellect")


def job(title, location, ident):
    return {"id": ident, "title": title, "locations": [location],
            "url": f"https://example.com/jobs/{ident}"}


class ExpansionTests(unittest.TestCase):
    def test_quant_us_software_only(self):
        postings = [
            job("Software Engineer Intern", "Chicago", "a"),
            job("Software Developer Intern", "New York", "b"),
            job("Quantitative Developer Intern", "London; Chicago", "c"),
            job("AI Engineer Intern", "Chicago", "d"),
            job("Quantitative Research Intern", "Chicago", "e"),
            job("Trading Intern", "New York", "f"),
            job("Software Engineer Intern", "Hong Kong", "g"),
            job("Software Engineer", "Chicago", "h"),
            job("Software Engineer Intern", "Amsterdam, Netherlands", "i"),
        ]
        with patch.object(quant, "greenhouse_jobs", return_value=postings):
            result = quant.quant_greenhouse_internships("test")
        self.assertEqual([j["id"] for j in result], ["a", "b", "c", "d"])
        self.assertEqual(result[0]["locations"], ["Chicago, IL"])
        self.assertEqual(result[2]["locations"], ["London", "Chicago, IL"])

    def test_prime_generic_technical_intern_not_growth(self):
        postings = [job("Internship", "San Francisco", "a"),
                    job("Growth Internship", "San Francisco, CA", "b"),
                    job("Software Engineer Intern", "San Francisco, CA", "c"),
                    job("Software Engineer", "San Francisco, CA", "d"),
                    job("Internship", "London", "e")]
        with patch.object(prime, "ashby_jobs", return_value=postings) as feed:
            self.assertEqual([j["id"] for j in prime.fetch_jobs()], ["a", "c"])
            feed.assert_called_once_with("PrimeIntellect")


if __name__ == "__main__":
    unittest.main()
