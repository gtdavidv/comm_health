# Submission Notes

## How to run

See [README.md](README.md) for the full setup walkthrough.

---

## Architecture

CommHealth is three Docker containers: a FastAPI backend, a PostgreSQL database, and a React frontend served by nginx. The nginx container also reverse-proxies `/api/` to the backend, so the frontend never talks to the API directly.

The backend is async throughout — FastAPI with asyncpg, httpx for Reddit calls, and AsyncOpenAI for the LLM — which keeps the event loop free during the slow Reddit pagination. Fetched posts and comments are persisted to Postgres and cached by exact (subreddit, from, to) range, so repeat queries are sub-second. Comments are fetched per-post rather than from the subreddit listing endpoint, which only returns the ~1000 most recent comments site-wide and misses most of a multi-day window on busy subreddits. The LLM narrative endpoint passes only pre-aggregated metrics to the model — no raw post titles or comment text — which constrains hallucination and keeps the prompt small.

---

## What I'd do next

- **OAuth Reddit access** — the public API caps pagination at ~1000 items and enforces a 1 req/sec rate limit. OAuth would raise both ceilings significantly and make larger date ranges practical.
- **Background sync** — right now the first request for a range is slow while the app paginates Reddit. A periodic worker that pre-fetches recent data for tracked subreddits would make the UI feel instant.
- **LLM-as-judge eval suite** — the eval harness ships with 10 deterministic structural checks and 10 commented-out tests that require a judge model to score semantic quality. Wiring those up is the natural next step before swapping models.
- **Subreddit comparison** — the data model supports it; the UI and a `/compare` endpoint do not yet exist.

---

## AI usage

I used AI thoroughly throughout this process. I used ChatGPT to summarize and pull out the most important points of the prompt itself, worked through the major architectural approach iteratively, and then had ChatGPT draft up a prompt to get the technical work started with Claude Code.

I used Claude Code in the CLI/terminal extensively to actually develop the application. I generally dictated system-level and feature-selection decisions (e.g., use React or SQLAlchemy / provide the users with date selectors for the Reddit API) while leaving code execution largely to the discretion of the LLM. I worked through features in a focused manner: drafting, testing, and iterating before moving to the next feature. I included AI review as a consistent step in that process, including occasional resets of the context window for fresh review.

In looking back over my transcript with Claude Code I pushed back or redirected regularly, particularly when it came to clarifying communication or fixing bugs. I was typically dictating higher level system design decisions or explicitly asking for perspective, so I didn't need to refine high level approach as much.