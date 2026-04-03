# CSES Problem Set API

A FastAPI-based REST API for interacting with the [CSES Problem Set](https://cses.fi/problemset/). Fetch problems, submit solutions, and track your progress.

## Setup

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

The API runs at `http://127.0.0.1:8000`. Interactive docs at `/docs`.

## Usage

All CSES-interacting endpoints require a `user_id` query parameter.

### 1. Authenticate

```bash
curl -X POST http://127.0.0.1:8000/auth/session \
  -H "Content-Type: application/json" \
  -d '{"username": "your_cses_username", "password": "your_cses_password"}'
```

### 2. Browse problems

```bash
curl "http://127.0.0.1:8000/problems?user_id=your_username"
curl "http://127.0.0.1:8000/problems/introductory-problems?user_id=your_username"
curl "http://127.0.0.1:8000/problems/introductory-problems/1068?user_id=your_username"
```

### 3. Submit a solution

```bash
curl -X POST "http://127.0.0.1:8000/problems/1068/submit?user_id=your_username&language=python3" \
  -F "file=@solution.py"
```

Supported languages: `python3`, `cpp`, `java`, `javascript`, `rust`, `c`, and more.

### 4. Track progress

```bash
curl "http://127.0.0.1:8000/progress?user_id=your_username"
```

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/session` | POST / DELETE | Create or close a CSES session |
| `/problems` | GET | List problem categories |
| `/problems/{category}` | GET | List problems in a category |
| `/problems/{category}/{problem_id}` | GET | Fetch problem details |
| `/problems/{problem_id}/submit` | POST | Submit a solution |
| `/progress` | GET | Get user progress |
| `/progress/submissions/{id}` | GET | Get a specific submission |
| `/health` | GET | Health check |

Rate limit: 30 requests/minute per client.

## Tests

```bash
pytest tests/ -v
```
