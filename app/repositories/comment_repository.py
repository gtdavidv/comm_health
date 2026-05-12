from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.reddit import RedditComment
from app.models.reddit import Comment


class CommentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, comments: list[RedditComment], fetched_at: datetime) -> None:
        if not comments:
            return
        rows = [
            {
                "reddit_id": c.reddit_id,
                "post_reddit_id": c.post_reddit_id,
                "subreddit": c.subreddit,
                "author": c.author,
                "body": c.body,
                "score": c.score,
                "created_utc": c.created_utc,
                "fetched_at": fetched_at,
            }
            for c in comments
        ]
        stmt = insert(Comment).values(rows)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_comments_reddit_id",
            set_={
                "score": stmt.excluded.score,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def get_for_posts(
        self,
        subreddit: str,
        post_reddit_ids: list[str],
    ) -> list[Comment]:
        if not post_reddit_ids:
            return []
        result = await self._session.execute(
            select(Comment).where(
                Comment.subreddit == subreddit.lower(),
                Comment.post_reddit_id.in_(post_reddit_ids),
            )
        )
        return list(result.scalars().all())
