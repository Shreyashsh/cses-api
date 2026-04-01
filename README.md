# CSES Problem Set API

API for fetching CSES problems, submitting solutions, and tracking progress.

## Setup

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

## API Docs

Open http://127.0.0.1:8000/docs for Swagger UI.

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/session` | POST | Initialize CSES session |
| `/problems` | GET | List problem categories |
| `/problems/{category}` | GET | List problems in category |
| `/problems/{category}/{id}` | GET | Fetch problem details |
| `/problems/{id}/submit` | POST | Submit solution file |
| `/progress` | GET | Get user progress |
| `/submissions/{id}` | GET | Get submission history |
