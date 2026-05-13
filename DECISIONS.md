# Technical Decisions

---

## Why these metrics

Healthy communities share a recognisable shape: broad participation, questions that get answered, and no single clique dominating the conversation. Each metric is chosen to make one dimension of that shape visible and quantifiable.

**`unique_contributors`** — Counts distinct post and comment authors (excluding `[deleted]`). A subreddit can generate 500 posts in a week and still be driven by 10 people. Without this, high activity is indistinguishable from broad participation. The interesting signal: a sharp drop here while post volume holds steady often means a community is consolidating around a core group.

**`engagement_concentration_pct`** — Percentage of all comments written by the top 5 users. Even a community with 1,000 contributors can be fragile if 3 of them write 60% of the comments — when those people leave, the community hollows out fast. This surfaces dependency risk that contributor counts alone hide. It's also a proxy for power dynamics: high concentration in a help subreddit usually means a few experts doing all the work.

**`unanswered_post_rate_pct`** — Percentage of posts with zero captured comments. This is the rejection signal. A post that goes unanswered is someone who showed up and was ignored. High rates correlate with churn — people post once, get nothing back, and don't return. It's a leading indicator of health problems that won't show up in volume metrics for weeks.

**`median_response_time_minutes`** — Time from post creation to first captured comment. Median rather than mean, because a handful of viral posts skew the mean badly. The most interesting use of this metric is the trend alert: if the median doubles in the second half of a period, the community is becoming less responsive even if post volume holds steady. That divergence — flat posts, rising response time — often signals moderator fatigue or audience drift.

**`avg_comments_per_post`** — Total comments divided by total posts. A subreddit where the average post gets 0.3 comments is a broadcast channel; one where the average gets 40 is a debate club. Same post volume, completely different community character. This sits between the other metrics as a quick readout of whether people are consuming content or participating in it.

---

## Technical decisions

Choices we made and what we traded away by making them.

---

## 1. Reddit public JSON API over OAuth2

We authenticate with Reddit using only a `User-Agent` header against the public `.json` endpoints. Reddit also offers an OAuth2 app flow that grants a proper access token.

**What we gain by not using OAuth2:** zero setup friction. No Reddit app registration, no client ID/secret, no token refresh logic. A new user is unblocked after editing a single line in `.env`.

**What we give up:** the unauthenticated API is rate-limited to roughly 1 request per second, versus 60 requests per minute for authenticated clients. For large subreddits or wide date ranges this directly lengthens the ingestion time on first fetch. OAuth2 would also unlock endpoints unavailable to anonymous clients.

**When to revisit:** if ingestion latency becomes a user-facing problem, adding OAuth2 is the lowest-effort fix and does not require any schema or architecture changes.

---

## 2. Synchronous ingestion inside the request handler

When a subreddit and date range have not been cached, the API fetches from Reddit, stores the results, and then returns — all within the same HTTP request. The client waits the full duration.

**What we gain:** simplicity. No worker process, no job queue, no polling endpoint, no additional infrastructure. The happy path (cache hit) is instant, and the slow path (cache miss) still completes and returns a result in a single round trip.

**What we give up:** requests that hit Reddit for the first time can block for 30–90 seconds. This exceeds what most HTTP clients and proxies will tolerate by default, and it holds an open database connection for the duration.

**The natural next step:** a task queue (Celery with Redis or a lightweight alternative) would let the endpoint return a job ID immediately. The client polls a `/jobs/{id}` endpoint until results are ready. The ingestion logic itself would not change.

---

## 3. PostgreSQL as the cache layer

Fetched posts, comments, and fetch records all live in the same PostgreSQL instance as the application data. Cache lookups are SQL range queries against the `fetch_records` table.

**What we gain:** one fewer infrastructure dependency. Postgres is already required, so using it for caching keeps the deployment at two containers and eliminates operational overhead for a separate cache store.

**What we give up:** Redis is significantly faster for simple key lookups, and it supports native TTL-based expiration without a cleanup job. Postgres also does not have a built-in mechanism to automatically evict stale fetch records — right now cached data never expires, so a subreddit queried in January will return January's data forever unless the records are manually deleted.

**When to revisit:** if cache invalidation (e.g. refreshing data after N days) or sub-millisecond cache reads become requirements, Redis is the straightforward addition.

---

## 4. SQLAlchemy over SQLModel

We use SQLAlchemy 2.0 with `mapped_column` for the ORM layer and separate Pydantic models for the API schemas. SQLModel, built on top of both, can collapse these into a single class definition.

**What we gain:** explicit separation between the database representation and the API contract. The two layers can evolve independently — a column can be added to the DB without appearing in the API response, and vice versa. SQLAlchemy 2.0's typed `Mapped` annotations also give full type-checker coverage without SQLModel's additional abstraction.

**What we give up:** more code. Every entity has both an ORM model and a Pydantic schema, and keeping them in sync is manual work. SQLModel would eliminate the duplication for straightforward cases.

---

## 5. Blocking HTTP response over Server-Sent Events

On a cache miss, the client receives no feedback until the full response is ready. The frontend shows a spinner and a static warning that the request may take up to a minute.

**What we gain:** a simple, standard HTTP request/response cycle. No streaming infrastructure, no connection keep-alive tuning, no client-side event listener logic.

**What we give up:** the user experience on slow fetches is poor. A progress stream — "fetching page 3 of posts… 127 posts found so far" — would make the wait feel intentional rather than broken. Server-Sent Events would be the natural fit: a single long-lived HTTP response where the server pushes progress lines until the result is ready.

---

## 6. Raw `fetch` over React Query

The frontend uses the browser's native `fetch` API with local `useState` for request state. React Query (TanStack Query) is the conventional choice for data fetching in React applications.

**What we gain:** no additional dependency, no library API to learn, explicit control over exactly what happens on each request.

**What we give up:** React Query provides caching, background refetching, deduplication of in-flight requests, and standardised loading/error/success states for free. With raw `fetch`, re-searching the same subreddit and date range makes a new network request every time. With React Query it would return the cached result instantly and optionally revalidate in the background.

---

## 7. Recomputing metrics on every request

The `compute_health` function runs over the raw posts and comments from the database on every API call. The computed result — total posts, response times, concentration, alerts — is not stored anywhere.

**What we gain:** the metrics are always computed from the latest cached data, and there is no risk of a stale pre-computed result being served.

**What we give up:** if computed metrics were stored in a `community_health_snapshots` table keyed by (subreddit, from_date, to_date), two things become possible: serving repeated queries instantly without re-running the calculation, and trend analysis across snapshots — for example, comparing this month's engagement concentration to last month's without re-fetching either period.

---

## 8. Plain JavaScript over TypeScript

The frontend is written in JSX with no type annotations. The backend is fully typed Python.

**What we gain:** lower setup overhead and a smaller cognitive gap for contributors who know React but not TypeScript. The frontend is small enough that the absence of types is not yet painful.

**What we give up:** the API contract between backend and frontend is not enforced at compile time. If a response field is renamed or a new required field is added, the frontend fails silently at runtime rather than loudly at build time. The natural fix — generating TypeScript types from the FastAPI OpenAPI schema — would close this gap and is a well-supported workflow.
