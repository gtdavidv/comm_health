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

---

## NOTES — Architecture & Tradeoffs

### Why these metrics

Healthy online communities share a recognizable shape: lots of people contribute, questions get answered quickly, and no single clique dominates the conversation. The metrics were chosen to make that shape visible and quantifiable.

`unique_contributors` and `engagement_concentration_pct` together answer the question of whether a community is genuinely broad or just appears busy because a few prolific users dominate. High volume with high concentration is a warning sign — the community looks active but is actually dependent on a small group.

`median_response_time_minutes` and `unanswered_post_rate_pct` capture whether the community is welcoming. A post that goes unanswered is a silent rejection. Rising response times over a period suggest the community is becoming less engaged, even if post volume stays constant — which is why a trend alert exists for it rather than just a threshold.

`avg_comments_per_post` sits between these two pairs: it reflects both how interesting the content is and how willing people are to engage with it. A subreddit where most posts get 0–1 comments is a very different place from one where most posts spark a thread.

### Reddit API pagination limit
Reddit's listing API (e.g. `/r/LocalLLaMA/new.json`) supports at most ~10 pages
of 100 items = **1000 posts per fetch**. For high-volume subreddits or long
historical ranges, this limit may result in incomplete data. The service is
transparent about this: metrics are computed on whatever data was captured, and
`median_response_time_minutes` is labelled as "time to first *captured* comment."

### Caching strategy
A `fetch_records` table tracks (subreddit, from_dt, to_dt) tuples. If a fetch
record covers the requested range, the DB is used directly; Reddit is never
re-called. This means the first call for a range is slow (Reddit pagination +
1-second delays); subsequent calls are sub-second.

### LLM grounding design
The narrative endpoint intentionally feeds only the pre-computed metric summary
to the LLM — not any raw post titles, bodies, or comment text. The system prompt
instructs the model to cite specific values from the input, constraining
hallucination. No metric values appear in the response that don't first appear
in the formatted metrics blob.

### Adding a new LLM provider
1. Implement `LLMProvider` (see `app/llm/base.py`)
2. Register it in `app/llm/factory.py`
3. Set `LLM_PROVIDER=<your_provider>` in `.env`

### Async throughout
All DB operations use `AsyncSession` (asyncpg driver), all HTTP calls use
`httpx.AsyncClient`, and all LLM calls use `AsyncOpenAI`. FastAPI's default
thread pool is never used for blocking I/O.
