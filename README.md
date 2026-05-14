# TalentScan - Candidate Assessment Dashboard

An internal candidate scoring and review dashboard built for Company's recruitment workflow. Reviewers can score candidates across categories and view AI-generated summaries, while admins get full visibility including internal notes.

## Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.12, FastAPI, aiosqlite |
| **Frontend** | React 19, Vite, React Router, Axios |
| **Database** | SQLite with WAL mode |
| **Auth** | JWT (PyJWT) + bcrypt password hashing |
| **Containerization** | Docker Compose |

---

## Quick Start

### Option 1: Docker Compose (Recommended)

**Prerequisites:** [Docker Desktop](https://docs.docker.com/desktop/install/) installed and running (verify with `docker --version`).

```bash
# Clone the repository
git clone https://github.com/ishwors/talent-evaluation-platform.git
cd talent-evaluation-platform

# Copy environment config and set a JWT secret
cp .env.example .env
# Edit .env → set JWT_SECRET_KEY to a secure value

# Build and start all services (detached mode)
docker compose up --build -d
```

**Verify everything is running:**

```bash
docker compose ps
# Expected:
# talentscan-backend     Up (healthy)    0.0.0.0:8000->8000/tcp
# talentscan-frontend    Up              0.0.0.0:5173->80/tcp
```

| Service | URL |
|---------|-----|
| **Frontend (Dashboard)** | <http://localhost:5173> |
| **Backend API** | <http://localhost:8000/api> |
| **API Docs (Swagger)** | <http://localhost:8000/docs> |

> **Database:** SQLite is embedded in the backend container — no separate setup needed. The database file and tables are created automatically on first startup. Data persists across restarts via a Docker named volume (`backend_data`).

**Useful commands:**

```bash
docker compose logs -f          # Follow live logs
docker compose logs backend     # Backend logs only
docker compose down             # Stop (preserves database)
docker compose down -v          # Stop and DELETE all data
docker compose up --build -d    # Rebuild after code changes
```

> **Common issue — port conflict:** If ports 5173 or 8000 are in use by local dev servers, stop them first or change the port mappings in `docker-compose.yml`.

### Option 2: Local Development

**Prerequisites:** Python 3.12+, Node.js 20+, npm 10+.

**1. Environment config:**

```bash
cp .env.example .env
# Edit .env → set JWT_SECRET_KEY to a secure value
```

**2. Backend:**

```bash
cd backend
python -m venv .venv

# Activate virtual environment:
.venv\Scripts\activate        # Windows (PowerShell)
source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**3. Frontend** (in a separate terminal):

```bash
cd frontend
npm install
npm run dev
```

**Verify:**

| Service | URL |
|---------|-----|
| **Frontend (Dashboard)** | <http://localhost:5173> |
| **Backend API** | <http://localhost:8000/api> |
| **API Docs (Swagger)** | <http://localhost:8000/docs> |

> **Database:** SQLite is used — no database installation needed. The `data/app.db` file and all tables are created automatically when the backend starts for the first time.

### Demo Credentials

Pre-seeded accounts are created on first startup:

| Role | Email | Password |
|---|---|---|
| **Admin** | <admin@ishwors.com> | admin123 |
| **Reviewer** | <reviewer@ishwors.com> | reviewer123 |

---

## Example API Calls

```bash
# Health check
curl http://localhost:8000/api/health

# Login (get JWT token)
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@ishwors.com", "password": "admin123"}'

# List candidates with filters
curl http://localhost:8000/api/candidates?status=new&page=1&page_size=10 \
  -H "Authorization: Bearer <token>"

# Get candidate detail
curl http://localhost:8000/api/candidates/<candidate_id> \
  -H "Authorization: Bearer <token>"

# Submit a score
curl -X POST http://localhost:8000/api/candidates/<candidate_id>/scores \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"category": "Technical Skills", "score": 4, "note": "Strong Python skills"}'

# Generate AI summary (takes ~2 seconds)
curl -X POST http://localhost:8000/api/candidates/<candidate_id>/summary \
  -H "Authorization: Bearer <token>"

# Register a new reviewer
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "New User", "email": "new@example.com", "password": "pass123"}'
```

---

## Running Tests

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

Tests cover:

1. **Registration role enforcement** — verifies role is always hardcoded to `reviewer`
2. **Candidate listing with authentication** — verifies auth is required and filters work
3. **Reviewer score isolation** — verifies a reviewer cannot see another reviewer's scores
4. **Admin full visibility** — verifies admin can see all scores and internal notes
5. **Internal notes access control** — verifies reviewer cannot see internal notes

---

## Debugging Signal — Bug Identification

### The Bug

```python
def search_candidates(status: str, keyword: str, page: int, page_size: int):
    all_candidates = db.execute("SELECT * FROM candidates").fetchall()
    filtered = [c for c in all_candidates if c["status"] == status]
    # ... also filter by keyword in Python ...
    offset = (page - 1) * page_size
    return filtered[offset : offset + page_size]
```

### What's Wrong

This code has **three critical issues**:

1. **Full table scan on every request.** `SELECT * FROM candidates` loads the entire table into memory before any filtering occurs. This defeats the purpose of pagination — the database returns *all* rows, Python filters them, and then slices a page. With 10,000 candidates, every paginated request loads 10,000 rows; with 1M candidates, it loads 1M rows.

2. **Filtering in Python instead of SQL.** The `status` and `keyword` filters are applied in Python using list comprehensions after fetching everything. The database has indexes on `status` and `role_applied` specifically to make these lookups fast — but they're completely bypassed. This is O(n) in Python instead of O(log n) with a B-tree index.

3. **No SQL-level LIMIT/OFFSET.** Pagination should be handled by the database using `LIMIT ? OFFSET ?` so it only transfers the rows needed for the current page. The current approach transfers the entire filtered result set over the DB connection and slices in Python.

### Why It Matters at Scale

- **Memory:** With 1M candidates, each request allocates ~1M row objects in memory, causing OOM errors or garbage collection pressure.
- **Latency:** Network transfer from DB → app for the full table adds significant latency even if the DB is fast.
- **Concurrency:** Under load, N concurrent users each load the full table = N × full_table_size in memory simultaneously.
- **Index waste:** Database indexes exist but are never used, wasting storage without benefit.

### The Correct Approach

```python
def search_candidates(status: str, keyword: str, page: int, page_size: int):
    conditions = ["deleted_at IS NULL"]
    params = []

    if status:
        conditions.append("status = ?")
        params.append(status)

    if keyword:
        conditions.append("(name LIKE ? OR email LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    where = " AND ".join(conditions)

    # Count for pagination metadata
    total = db.execute(f"SELECT COUNT(*) FROM candidates WHERE {where}", params).fetchone()[0]

    # Fetch only the current page
    offset = (page - 1) * page_size
    rows = db.execute(
        f"SELECT * FROM candidates WHERE {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [page_size, offset]
    ).fetchall()

    return {"candidates": rows, "total": total}
```

This pushes all filtering and pagination to SQL, leveraging indexes and transferring only the rows needed.

---

## Architecture Decision Records (ADR)

### ADR 1: SQLite over DynamoDB

**Context:** The project allows "DynamoDB-style or SQLite." Both are viable for this use case.

**Decision:** I chose SQLite with the `aiosqlite` async driver.

**Trade-off:** SQLite doesn't support true multi-writer concurrency or horizontal scaling. However, for a small project running locally or in a single Docker container, it's the pragmatic choice:

- Zero infrastructure setup (no DynamoDB Local, no AWS credentials)
- WAL mode enables concurrent readers with a single writer
- Full SQL support means indexes, JOINs, and WHERE clauses work naturally
- `aiosqlite` provides async I/O, keeping FastAPI's event loop non-blocking

In production, I'd use DynamoDB with GSIs for `status` and `role_applied`, keeping the same service layer interface.

### ADR 2: JWT with bcrypt for Authentication

**Context:** The app needs role-based access control with two roles (reviewer, admin).

**Decision:** Stateless JWT tokens with bcrypt-hashed passwords. The role is encoded in the JWT payload and validated on each request.

**Trade-off:** Stateless JWTs can't be revoked until they expire (no server-side session store). For an internal tool with trusted users, this is acceptable. The 8-hour expiry provides reasonable security without forcing frequent re-authentication. Registration hardcodes the role to `reviewer` — admin accounts must be created via seed data or direct DB access, preventing privilege escalation.

### ADR 3: Soft Delete with `deleted_at` Timestamp

**Context:** The project requires that candidates are never hard-deleted.

**Decision:** Added a `deleted_at` column to the candidates table. All queries include `WHERE deleted_at IS NULL` to exclude archived candidates. The delete endpoint sets `deleted_at` and changes status to `archived`.

**Trade-off:** Soft deletes increase storage over time and require every query to filter on `deleted_at`. An index on `deleted_at` mitigates the query performance impact. This is the standard approach for audit-compliant systems where data recovery and history tracking are important.

---

## Learning Reflection

I was implementing **Server-Sent Events (SSE)** in FastAPI for the stretch-goal real-time score streaming endpoint. I found that FastAPI's `StreamingResponse` with async generators maps very cleanly to the SSE protocol — the pattern of yielding `data: ...\n\n` formatted strings is elegant. In production, I'd back this with a proper pub/sub mechanism (Redis Pub/Sub or DynamoDB Streams + EventBridge) instead of database polling, but the SSE transport layer would remain the same. Given more time, I'd also explore WebSocket connections for bidirectional communication and implement optimistic UI updates on the frontend to make score submission feel instantaneous.

---

## Project Structure

```
/
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI app, lifespan, seed data
│   │   ├── models.py            # SQLite schema, indexes, DB connection
│   │   ├── schemas.py           # Pydantic request/response models
│   │   ├── auth.py              # JWT, bcrypt, auth dependencies
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # Register, login, /me endpoints
│   │   │   └── candidates.py    # CRUD, scoring, AI summary, SSE
│   │   └── services/
│   │       ├── __init__.py
│   │       └── candidate_service.py  # Business logic, DB queries
│   └── tests/
│       ├── __init__.py
│       └── test_api.py          # API + auth enforcement tests
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx              # Router, protected routes
        ├── index.css            # Full design system
        ├── api/
        │   └── client.js        # Axios client with JWT interceptor
        └── pages/
            ├── LoginPage.jsx
            ├── CandidateListPage.jsx
            └── CandidateDetailPage.jsx
```

---

## Limitations & Honest Acknowledgments

- **SSE polling-based:** The real-time streaming endpoint polls the database every 2 seconds rather than using a proper pub/sub system. In production, I'd use Redis Pub/Sub or DynamoDB Streams.
- **No refresh tokens:** The current auth implementation uses only access tokens. A production system would include refresh token rotation.
- **No rate limiting:** API endpoints have no request throttling. In production, I'd add `slowapi` middleware or use an API gateway (e.g., AWS API Gateway, Cloudflare) with rate limiting rules to prevent brute-force login attempts and endpoint abuse.
- **SQLite concurrency:** SQLite supports one writer at a time. For a multi-user production deployment, I'd switch to PostgreSQL or DynamoDB.
- **Basic keyword search:** The current search uses SQL `LIKE` which doesn't support full-text search. For better search, I'd add SQLite FTS5 or use Elasticsearch.

---
