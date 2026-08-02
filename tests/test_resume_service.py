import unittest
from io import BytesIO

from fastapi.testclient import TestClient

from app import app
from resume_service import build_bulk_rankings, build_heuristic_result


class ResumeServiceTests(unittest.TestCase):
    def test_build_heuristic_result_returns_scored_summary(self):
        resume_text = "I have strong Python and Flask experience with AWS deployment."
        result = build_heuristic_result(resume_text)

        self.assertGreaterEqual(result["match_percentage"], 0)
        self.assertLessEqual(result["match_percentage"], 100)
        self.assertIn("Python", result["matched_skills"])
        self.assertIn("Flask", result["matched_skills"])
        self.assertTrue(result["summary"])

    def test_build_bulk_rankings_sorts_candidates_descending(self):
        rankings = build_bulk_rankings([
            {"candidate_name": "Ada", "match_percentage": 70, "matched_skills": ["Python"], "missing_skills": ["AWS"]},
            {"candidate_name": "Ben", "match_percentage": 88, "matched_skills": ["Python", "AWS"], "missing_skills": []},
        ])

        self.assertEqual(rankings[0]["candidate_name"], "Ben")
        self.assertEqual(rankings[0]["rank"], 1)
        self.assertEqual(rankings[1]["candidate_name"], "Ada")
        self.assertEqual(rankings[1]["rank"], 2)

    def test_home_route_serves_polished_template(self):
        client = TestClient(app)
        response = client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("AI-assisted recruiting intelligence", response.text)

    def test_analyze_single_route_accepts_pdf_upload(self):
        client = TestClient(app)
        payload = BytesIO(b"%PDF-1.4\n%fake pdf")
        response = client.post(
            "/api/analyze-single",
            files={"file": ("candidate.pdf", payload, "application/pdf")},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("match_percentage", response.json())


if __name__ == "__main__":
    unittest.main()
