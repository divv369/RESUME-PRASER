# Resume Match Studio

This project now includes a simple frontend and backend for uploading a PDF resume and getting a match score for a software engineering role.

## Run locally

```bash
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Then open http://127.0.0.1:8000/

## Deploy to Vercel

1. Push this folder to GitHub.
2. Import the repository in Vercel.
3. Vercel will use the included vercel.json configuration.
4. Set the environment variable GROQ_API_KEY if you want to use the LLM-powered path.

## Notes

- The app accepts PDF uploads and returns a lightweight match analysis.
- If GROQ_API_KEY is not configured, it falls back to a heuristic analysis so the app still works.
