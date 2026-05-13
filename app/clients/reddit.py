import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
import structlog
from json import JSONDecodeError

log = structlog.get_logger(__name__)

BASE_URL = "https://www.reddit.com"
MAX_PAGINATION_DEPTH = 10  # Reddit caps at ~1000 items per listing


@dataclass(frozen=True)
class RedditPost:
    reddit_id: str
    subreddit: str
    title: str
    author: str
    score: int
    num_comments: int
    created_utc: datetime


@dataclass(frozen=True)
class RedditComment:
    reddit_id: str
    post_reddit_id: str
    subreddit: str
    author: str
    body: str
    score: int
    created_utc: datetime


class RedditAPIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        super().__init__(f"Reddit API error {status_code}: {message}")


class RedditClient:
    def __init__(self, user_agent: str, request_delay: float = 1.0) -> None:
        self._user_agent = user_agent
        self._request_delay = request_delay
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "RedditClient":
        self._client = httpx.AsyncClient(
            headers={"User-Agent": self._user_agent},
            timeout=30.0,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("RedditClient must be used as an async context manager")
        return self._client

    async def _get(self, path: str, params: dict) -> dict | list:
        params["raw_json"] = 1
        try:
            response = await self.client.get(f"{BASE_URL}{path}", params=params)
        except httpx.RequestError as exc:
            raise RedditAPIError(0, f"Network error contacting Reddit: {exc}") from exc
        if response.status_code == 404:
            raise RedditAPIError(404, "Subreddit not found")
        if response.status_code == 403:
            raise RedditAPIError(403, "Subreddit is private or restricted")
        if response.status_code == 429:
            raise RedditAPIError(429, "Rate limited by Reddit API")
        if response.status_code >= 400:
            raise RedditAPIError(response.status_code, f"Reddit returned {response.status_code}")
        try:
            return response.json()
        except JSONDecodeError as exc:
            raise RedditAPIError(0, "Reddit returned an unexpected response") from exc

    async def fetch_posts(
        self,
        subreddit: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> list[RedditPost]:
        """Paginate /r/{subreddit}/new until posts fall before from_dt."""
        posts: list[RedditPost] = []
        after: str | None = None

        for page in range(MAX_PAGINATION_DEPTH):
            params: dict = {"limit": 100}
            if after:
                params["after"] = after

            data = await self._get(f"/r/{subreddit}/new.json", params)
            children = data["data"]["children"]

            if not children:
                break

            for child in children:
                d = child["data"]
                created = datetime.fromtimestamp(d["created_utc"], tz=timezone.utc)

                if created > to_dt:
                    continue
                if created < from_dt:
                    log.debug("reached_from_boundary", page=page, subreddit=subreddit)
                    return posts

                author = d.get("author") or "[deleted]"
                posts.append(
                    RedditPost(
                        reddit_id=d["id"],
                        subreddit=subreddit.lower(),
                        title=d.get("title", ""),
                        author=author,
                        score=d.get("score", 0),
                        num_comments=d.get("num_comments", 0),
                        created_utc=created,
                    )
                )

            after = data["data"].get("after")
            if not after:
                break

            log.debug("fetching_next_post_page", page=page + 1, after=after)
            await asyncio.sleep(self._request_delay)

        return posts

    async def fetch_comments_for_post(
        self,
        subreddit: str,
        post_id: str,
    ) -> list[RedditComment]:
        """Fetch all comments for a single post via its dedicated endpoint."""
        try:
            data = await self._get(
                f"/r/{subreddit}/comments/{post_id}.json",
                {"limit": 500},
            )
        except RedditAPIError:
            return []

        if not isinstance(data, list) or len(data) < 2:
            return []

        comments: list[RedditComment] = []
        self._collect_comments(data[1]["data"]["children"], subreddit, post_id, comments)
        return comments

    def _collect_comments(
        self,
        children: list[dict],
        subreddit: str,
        post_id: str,
        acc: list[RedditComment],
    ) -> None:
        """Recursively walk a comment tree, collecting all t1 nodes."""
        for child in children:
            if child.get("kind") != "t1":
                continue
            d = child["data"]
            raw_ts = d.get("created_utc")
            if raw_ts is None:
                continue
            acc.append(
                RedditComment(
                    reddit_id=d["id"],
                    post_reddit_id=post_id,
                    subreddit=subreddit.lower(),
                    author=d.get("author") or "[deleted]",
                    body=d.get("body", ""),
                    score=d.get("score", 0),
                    created_utc=datetime.fromtimestamp(raw_ts, tz=timezone.utc),
                )
            )
            replies = d.get("replies")
            if isinstance(replies, dict):
                self._collect_comments(
                    replies.get("data", {}).get("children", []),
                    subreddit,
                    post_id,
                    acc,
                )
