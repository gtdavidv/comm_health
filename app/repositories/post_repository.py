from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.reddit import RedditPost
from app.models.reddit import Post


class PostRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, posts: list[RedditPost], fetched_at: datetime) -> None:
        if not posts:
            return
        rows = [
            {
                "reddit_id": p.reddit_id,
                "subreddit": p.subreddit,
                "title": p.title,
                "author": p.author,
                "score": p.score,
                "num_comments": p.num_comments,
                "created_utc": p.created_utc,
                "fetched_at": fetched_at,
            }
            for p in posts
        ]
        stmt = insert(Post).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_posts_reddit_id",
            set_={
                "score": stmt.excluded.score,
                "num_comments": stmt.excluded.num_comments,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_in_range(
        self,
        subreddit: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> list[Post]:
        result = await self._session.execute(
            select(Post).where(
                Post.subreddit == subreddit.lower(),
                Post.created_utc >= from_dt,
                Post.created_utc <= to_dt,
            )
        )
        return list(result.scalars().all())
