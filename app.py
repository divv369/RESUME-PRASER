from pathlib import Path
from typing import Any

from fastapi import File, Form, FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response

from resume_service import analyze_resume_file, build_bulk_rankings, build_export_payload

app = FastAPI(title="Resume Match App", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HTML_PAGE = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Resume Match Studio</title>
  <style>
    :root { color-scheme: dark; }
    body { margin: 0; font-family: Arial, sans-serif; background: linear-gradient(135deg, #07111f, #10233f); color: #f5f7fb; }
    .container { max-width: 980px; margin: 0 auto; padding: 48px 24px 72px; }
    .hero { background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.12); border-radius: 24px; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,0.25); }
    h1 { font-size: 2.3rem; margin-bottom: 10px; }
    p { line-height: 1.6; color: #dce7f8; }
    .upload-box { margin-top: 24px; border: 2px dashed #6ea8ff; border-radius: 16px; padding: 24px; background: rgba(255,255,255,0.05); }
    input[type=file] { margin-top: 12px; }
    button { background: linear-gradient(90deg, #4f8cff, #6b5cff); color: white; border: none; border-radius: 999px; padding: 12px 20px; cursor: pointer; font-weight: 600; margin-top: 14px; }
    .result { margin-top: 28px; padding: 20px; border-radius: 16px; background: rgba(255,255,255,0.06); }
    .pill { display: inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(79,140,255,0.2); margin: 4px 6px 0 0; }
  </style>
</head>
<body>
  <div class=\"container\">
    <div class=\"hero\">
      <h1>Resume Match Studio</h1>
      <p>Upload a candidate PDF and get an instant match score for a software engineering role. The result is generated directly in the browser and can be deployed as a lightweight web app.</p>
      <div class=\"upload-box\">
        <form id=\"uploadForm\" enctype=\"multipart/form-data\">
          <label for=\"file\">Choose a PDF resume</label>
          <input id=\"file\" name=\"file\" type=\"file\" accept=\".pdf\" required />
          <button type=\"submit\">Analyze Resume</button>
        </form>
      </div>
      <div id=\"result\" class=\"result\" style=\"display:none;\"></div>
    </div>
  </div>
  <script>
    const form = document.getElementById('uploadForm');
    const result = document.getElementById('result');

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const fileInput = document.getElementById('file');
      const file = fileInput.files[0];
      if (!file) return;

      const formData = new FormData();
      formData.append('file', file);

      result.style.display = 'block';
      result.innerHTML = '<p>Analyzing your resume...</p>';

      try {
        const response = await fetch('/analyze', { method: 'POST', body: formData });
        const data = await response.json();
        result.innerHTML = `
          <h3>Result</h3>
          <p><strong>Verdict:</strong> ${data.verdict}</p>
          <p><strong>Match Percentage:</strong> ${data.match_percentage}%</p>
          <p><strong>Summary:</strong> ${data.summary}</p>
          <p><strong>Matched Skills:</strong> ${data.matched_skills.map(skill => '<span class=\"pill\">' + skill + '</span>').join('')}</p>
          <p><strong>Missing Skills:</strong> ${data.missing_skills.length ? data.missing_skills.join(', ') : 'None'}</p>
        `;
      } catch (error) {
        result.innerHTML = '<p>Something went wrong while analyzing the resume.</p>';
      }
    });
  </script>
</body>
</html>
"""


ROOT = Path(__file__).resolve().parent
TEMPLATE_PATH = ROOT / "templates" / "index.html"


def _load_frontend_page() -> str:
    return TEMPLATE_PATH.read_text(encoding="utf-8")


def _enrich_analysis_result(result: dict[str, Any], *, job_description: str | None, use_default_description: bool) -> dict[str, Any]:
    match_score = float(result.get("match_percentage", 0) or 0)
    skills = [str(skill) for skill in result.get("matched_skills", [])]
    missing = [str(skill) for skill in result.get("missing_skills", [])]
    upgrade_focus = [
        "Highlight measurable delivery impact in your summary.",
        "Call out cloud, API, or product work more explicitly.",
        "Add one concrete project example tied to the role requirements.",
    ]
    if missing:
        upgrade_focus.append(f"Prioritize the missing skills: {', '.join(missing[:3])}.")

    return {
        **result,
        "ats_score": max(0, min(100, int(round(match_score + (10 if skills else 0))))) if result.get("ats_score") is None else result.get("ats_score"),
        "improvement_suggestions": upgrade_focus,
        "recruiter_verdict": result.get("verdict", "Needs review"),
        "final_recommendation": "Strong candidate for a first-round screen." if match_score >= 75 else "Useful follow-up candidate if the role is flexible." if match_score >= 50 else "Needs a stronger alignment story before advancing.",
        "job_description": job_description or "",
        "use_default_description": use_default_description,
    }


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(_load_frontend_page())


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)) -> JSONResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    try:
        content = await file.read()
        result = analyze_resume_file(content, file.filename)
        return JSONResponse(content=_enrich_analysis_result(result, job_description=None, use_default_description=True))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze-single")
async def analyze_single(
    file: UploadFile = File(...),
    job_description: str | None = Form(default=None),
    use_default_description: bool = Form(default=True),
) -> JSONResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")

    try:
        content = await file.read()
        result = analyze_resume_file(content, file.filename)
        return JSONResponse(content=_enrich_analysis_result(result, job_description=job_description, use_default_description=use_default_description))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/analyze-bulk")
async def analyze_bulk(
    files: list[UploadFile] = File(...),
    job_description: str | None = Form(default=None),
    use_default_description: bool = Form(default=True),
) -> JSONResponse:
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one PDF file")

    try:
        results = []
        for upload in files:
            if not upload.filename or not upload.filename.lower().endswith(".pdf"):
                continue
            content = await upload.read()
            payload = analyze_resume_file(content, upload.filename)
            payload = _enrich_analysis_result(payload, job_description=job_description, use_default_description=use_default_description)
            payload["candidate_name"] = upload.filename
            results.append(payload)

        return JSONResponse(content={"results": build_bulk_rankings(results)})
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/export-report")
async def export_report(payload: dict[str, Any]) -> Response:
    fmt = payload.get("format", "json")
    report = build_export_payload(payload.get("payload", {}), fmt)
    media_type = "application/json" if fmt in {"json", "pdf"} else "text/csv"
    return Response(content=report, media_type=media_type)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
