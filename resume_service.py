import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader

try:
    from groq import Groq
except Exception:  # pragma: no cover - optional dependency
    Groq = None


DEFAULT_JOB_DESCRIPTION = """
We are hiring a software engineer with strong Python, cloud, and product sense.
Candidates should have experience building scalable services, APIs, and deploying on AWS or similar platforms.
"""

MODEL = "llama-3.3-70b-versatile"
CLIENT = None

try:
    import os

    api_key = os.getenv("GROQ_API_KEY")
    if api_key and Groq is not None:
        CLIENT = Groq(api_key=api_key)
except Exception:  # pragma: no cover - environment dependent
    CLIENT = None

SKILL_LIBRARY = [
    "python",
    "sql",
    "aws",
    "docker",
    "flask",
    "fastapi",
    "javascript",
    "react",
    "typescript",
    "machine learning",
    "ai",
    "cloud",
    "kubernetes",
]
REQUIRED_SKILLS = ["python", "aws", "sql"]


def build_heuristic_result(resume_text: str) -> dict[str, Any]:
    text = (resume_text or "").lower()
    matched_skills = [skill for skill in SKILL_LIBRARY if skill in text]
    missing_skills = [skill for skill in REQUIRED_SKILLS if skill not in text]

    experience_years = 0.0
    year_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(year|years|yr|yrs)", text)
    if year_matches:
        experience_years = float(year_matches[0][0])

    score = min(100, max(20, 50 + len(matched_skills) * 7 - len(missing_skills) * 4))
    if experience_years >= 2:
        score += 5
    if "project" in text or "experience" in text:
        score += 3

    summary = (
        "The resume shows solid alignment with software engineering roles, especially around "
        + ", ".join(matched_skills[:3] or ["core engineering fundamentals"]) + "."
    )

    return {
        "match_percentage": round(min(100, score), 1),
        "matched_skills": [skill.title() for skill in matched_skills],
        "missing_skills": [skill.title() for skill in missing_skills],
        "summary": summary,
        "verdict": "Strong fit" if score >= 75 else "Needs improvement" if score >= 50 else "Weak fit",
        "experience_years": round(experience_years, 1),
    }


def analyze_resume_text(resume_text: str, use_llm: bool = True) -> dict[str, Any]:
    if use_llm and CLIENT is not None:
        try:
            prompt = (
                "You are an HR assistant. Compare the candidate resume against a software engineering role. "
                "Return a JSON object with keys: match_percentage, matched_skills, missing_skills, summary, verdict."
            )
            response = CLIENT.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": resume_text[:4000]},
                ],
                response_format={"type": "json_object"},
            )
            payload = json.loads(response.choices[0].message.content)
            if payload.get("match_percentage") is not None:
                return payload
        except Exception:
            pass

    return build_heuristic_result(resume_text)


def read_pdf_bytes(file_bytes: bytes) -> str:
    try:
        reader = PdfReader(BytesIO(file_bytes))
    except Exception:
        return ""

    text = ""
    for page in reader.pages:
        try:
            page_text = page.extract_text()
        except Exception:
            page_text = None
        if page_text:
            text += page_text + "\n"
    return text


def read_pdf(path: str | Path) -> str:
    try:
        reader = PdfReader(str(path))
    except Exception:
        return ""

    text = ""
    for page in reader.pages:
        try:
            page_text = page.extract_text()
        except Exception:
            page_text = None
        if page_text:
            text += page_text + "\n"
    return text


def analyze_resume_file(file_bytes: bytes, filename: str) -> dict[str, Any]:
    if filename.lower().endswith(".pdf"):
        text = read_pdf_bytes(file_bytes)
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
    return analyze_resume_text(text)


def build_bulk_rankings(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for index, result in enumerate(sorted(results, key=lambda item: item.get("match_percentage", 0), reverse=True), start=1):
        ranked.append(
            {
                "rank": index,
                "candidate_name": result.get("candidate_name") or f"Candidate {index}",
                "match_percentage": result.get("match_percentage", 0),
                "score": result.get("score", result.get("match_percentage", 0)),
                "skills_score": result.get("skills_score", 0),
                "experience_score": result.get("experience_score", 0),
                "education_score": result.get("education_score", 0),
                "missing_skills_count": len(result.get("missing_skills", [])),
            }
        )
    return ranked


def build_export_payload(payload: dict[str, Any], fmt: str) -> str:
    if fmt == "json":
        return json.dumps(payload, indent=2)
    if fmt == "csv":
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["field", "value"])
        for key, value in payload.items():
            writer.writerow([key, value])
        return output.getvalue()
    return json.dumps(payload, indent=2)
