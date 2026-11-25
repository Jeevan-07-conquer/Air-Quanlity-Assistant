# Urban Air Quality Assistant

Implementation following the Software Requirements Document (SRD v1.0).

## Stack
- Backend: Python 3.13 + Starlette + Pydantic + Uvicorn
- AI SDK: `google-genai` (server-side structured JSON output)
- Frontend: Semantic HTML + CSS Design Tokens + Modular Vanilla ES6 JS

## Run locally
```powershell
python -m uvicorn app.main:app --reload --port 8000
```

## Run tests
```powershell
python -m unittest discover -s tests -v
```
