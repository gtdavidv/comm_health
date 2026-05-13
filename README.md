# CommHealth — Reddit Community Analytics

Ingest public Reddit activity and expose community health insights.

Runs as three Docker containers: a FastAPI server, a React server, and a PostgreSQL database.

---

## Setup

### Step 1 — Clone the repo

```bash
git clone https://github.com/gtdavidv/comm_health.git
cd comm_health
```

### Step 2 — Get a Reddit account

CommHealth uses Reddit's public API. No API key or OAuth is needed, but Reddit requires identification with a real Reddit username.

### Step 3 — Get an OpenAI account / API key

Generated at https://platform.openai.com/api-keys. Required if you use the `/api/narrative` endpoint.

### Step 4 — Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` and fill in the required values:

| Variable | What to put |
|---|---|
| `POSTGRES_USER` | A PostgreSQL username (e.g. `commhealth`) |
| `POSTGRES_PASSWORD` | A strong password of your choice |
| `REDDIT_USER_AGENT` | `python:commhealth-analytics:v0.1.0 (by /u/<your_reddit_username>)` with your Reddit username substituted in |
| `OPENAI_API_KEY` | Your OpenAI API key. Only required if you use the narrative feature. |

### Step 5 — Start the containers

```bash
docker compose up --build
```

This starts three containers:

`commhealth-frontend` - React UI served by nginx (5173)
`commhealth-api` - FastAPI server (8765)
`commhealth-db` - PostgreSQL (15432)

Database migrations run automatically on startup.

### Step 6 — Open the app

Navigate to http://localhost:5173 in your browser.

> **Note:** The first request to `/api/insights` or `/api/narrative` for a given subreddit and date range will be slow — anywhere from 30 seconds to a few minutes — while CommHealth paginates through Reddit's API. Subsequent requests for the same range return immediately from the local database.

---

## API Reference

### `GET /api/insights/community-health`

Fetches Reddit data for the requested range (cached after first call) and returns
computed engagement metrics and rule-based alerts.

**Query parameters:**

| Param       | Type       | Required | Description                         |
|-------------|------------|----------|-------------------------------------|
| `subreddit` | string     | ✓        | Subreddit name (without `r/`)       |
| `from`      | ISO date   | ✓        | Start of range (e.g. `2026-04-01`) |
| `to`        | ISO date   | ✓        | End of range (e.g. `2026-04-30`)   |

**Example:**

```bash
curl "http://localhost:8765/api/insights/community-health?subreddit=LocalLLaMA&from=2026-04-01&to=2026-04-30"
```

**Response:**

```json
{
  "subreddit": "LocalLLaMA",
  "from_date": "2026-04-01",
  "to_date": "2026-04-30",
  "total_posts": 342,
  "total_comments": 4821,
  "unique_contributors": 892,
  "avg_comments_per_post": 14.09,
  "median_response_time_minutes": 23.5,
  "engagement_concentration_pct": 18.3,
  "unanswered_post_rate_pct": 8.2,
  "top_contributors": [
    {"username": "user_abc", "comment_count": 87, "post_count": 3, "total_contributions": 90}
  ],
  "alerts": [],
  "computed_at": "2026-05-12T10:00:00Z"
}
```

**Possible alerts:**

| Code                        | Triggers when                                                        |
|-----------------------------|----------------------------------------------------------------------|
| `HIGH_CONCENTRATION`        | Top 5 users account for ≥40% (warning) or ≥60% (critical) of comments |
| `HIGH_UNANSWERED_POST_RATE` | ≥30% (warning) or ≥50% (critical) of posts have zero comments        |
| `RESPONSE_TIME_INCREASE`    | Median response time in second half of period is ≥1.5x the first half |

---

### `POST /api/narrative/community-summary`

Computes the same metrics as the insights endpoint, then passes **only the
aggregated metrics** (not raw Reddit content) to an LLM for narrative generation.

**Request body:**

```json
{
  "subreddit": "LocalLLaMA",
  "from": "2026-04-01",
  "to": "2026-04-30"
}
```

**Example:**

```bash
curl -X POST http://localhost:8765/api/narrative/community-summary \
  -H "Content-Type: application/json" \
  -d '{"subreddit": "LocalLLaMA", "from": "2026-04-01", "to": "2026-04-30"}'
```

**Response:**

```json
{
  "subreddit": "LocalLLaMA",
  "from_date": "2026-04-01",
  "to_date": "2026-04-30",
  "summary": "r/LocalLLaMA demonstrated strong community engagement in April 2026, with 342 posts generating 4,821 comments from 892 unique contributors. The median response time of 23.5 minutes and low engagement concentration of 18.3% point to a healthy, distributed discussion culture.",
  "confidence": 0.92,
  "evidence": [
    {"metric": "total_posts", "value": 342, "interpretation": "High post volume indicates active community"},
    {"metric": "engagement_concentration_pct", "value": 18.3, "interpretation": "Low concentration; broad participation"},
    {"metric": "median_response_time_minutes", "value": 23.5, "interpretation": "Fast response times indicate engaged readership"}
  ]
}
```

---

### `GET /health`

```bash
curl http://localhost:8765/health
# {"status": "ok"}
```

---

## Environment Variables

| Variable               | Default                            | Description                                      |
|------------------------|------------------------------------|--------------------------------------------------|
| `POSTGRES_USER`        | —                                  | Required. PostgreSQL username                    |
| `POSTGRES_PASSWORD`    | —                                  | Required. PostgreSQL password                    |
| `POSTGRES_DB`          | `commhealth`                       | PostgreSQL database name                         |
| `DATABASE_URL`         | —                                  | Required. Full async connection string — set this to `postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@commhealth-db:5432/${POSTGRES_DB}` |
| `REDDIT_USER_AGENT`    | —                                  | Required. Format: `platform:app:version (by /u/username)` |
| `REDDIT_REQUEST_DELAY` | `1.0`                              | Seconds between paginated Reddit requests        |
| `LLM_PROVIDER`         | `openai`                           | LLM backend (`openai` only currently)            |
| `OPENAI_API_KEY`       | —                                  | Required for narrative endpoint                  |
| `OPENAI_MODEL`         | `gpt-4o-mini`                      | Model to use for narrative generation            |
| `LOG_LEVEL`            | `INFO`                             | `DEBUG`, `INFO`, `WARNING`, `ERROR`              |
| `ENVIRONMENT`          | `development`                      | `development` → colored logs; `production` → JSON |

---

## Running Tests

```bash
docker compose run --rm commhealth-api pytest tests/ -v
```

Tests cover:
- Metric calculations (avg comments, response time, contributor counts)
- Alert rule thresholds (concentration, unanswered rate, response time trend)
- Narrative grounding (LLM receives metrics, not raw Reddit data)

No database or network connection is required by the test suite.

### Eval suite

```bash
docker compose run --rm commhealth-api pytest evals/ -v
```

Evals make real calls to the LLM and assert deterministic properties of its output — structure, numeric grounding, and confidence thresholds. Requires `OPENAI_API_KEY` to be set in `.env`.

---

## Project Structure

```
app/
├── api/routes/         # FastAPI route handlers
├── clients/            # External API clients (Reddit)
├── config/             # Pydantic settings
├── db/                 # SQLAlchemy engine & session factory
├── llm/                # LLM provider abstraction + OpenAI implementation
├── models/             # SQLAlchemy ORM models
├── repositories/       # DB access layer (upserts, range queries)
├── schemas/            # Pydantic request/response models
└── services/           # Business logic (ingestion, metrics, narrative)

migrations/             # Alembic migrations
tests/                  # Pytest test suite
```
