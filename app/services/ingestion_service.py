import asyncio
from datetime import datetime, timezone

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.reddit import RedditClient, RedditComment
from app.config.settings import settings
from app.repositories.comment_repository import CommentRepository
from app.repositories.fetch_repository import FetchRepository
from app.repositories.post_repository import PostRepository

log = structlog.get_logger(__name__)


class IngestionService:
    def __init__(self, session: AsyncSession) -> None:
        self._post_repo = PostRepository(session)
        self._comment_repo = CommentRepository(session)
        self._fetch_repo = FetchRepository(session)

    async def ensure_data(
        self,
        subreddit: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> tuple[int, int]:
        """
        Ensure DB has data for [from_dt, to_dt]. Fetches from Reddit only when
        the range is not already cached. Returns (post_count, comment_count).
        """
        if await self._fetch_repo.has_coverage(subreddit, from_dt, to_dt):
            log.info("cache_hit", subreddit=subreddit)
            posts = await self._post_repo.get_in_range(subreddit, from_dt, to_dt)
            comments = await self._comment_repo.get_for_posts(
                subreddit, [p.reddit_id for p in posts]
            )
            return len(posts), len(comments)

        log.info("cache_miss_fetching", subreddit=subreddit, from_dt=from_dt, to_dt=to_dt)
        fetched_at = datetime.now(tz=timezone.utc)

        async with RedditClient(settings.reddit_user_agent, settings.reddit_request_delay) as client:
            posts = await client.fetch_posts(subreddit, from_dt, to_dt)
            log.info("posts_fetched", count=len(posts), subreddit=subreddit)

            posts_needing_comments = [p for p in posts if p.num_comments > 0]
            all_comments: list[RedditComment] = []
            for i, post in enumerate(posts_needing_comments):
                post_comments = await client.fetch_comments_for_post(subreddit, post.reddit_id)
                all_comments.extend(post_comments)
                if i < len(posts_needing_comments) - 1:
                    await asyncio.sleep(settings.reddit_request_delay)
            comments = all_comments
            log.info("comments_fetched", count=len(comments), post_count=len(posts_needing_comments), subreddit=subreddit)

        await self._post_repo.upsert(posts, fetched_at)
        await self._comment_repo.upsert(comments, fetched_at)
        await self._fetch_repo.record(
            subreddit, from_dt, to_dt, len(posts), len(comments), fetched_at
        )

        return len(posts), len(comments)
