from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reddit import FetchRecord


class FetchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def has_coverage(
        self,
        subreddit: str,
        from_dt: datetime,
        to_dt: datetime,
    ) -> bool:
        """Return True if a prior fetch already covers [from_dt, to_dt]."""
        result = await self._session.execute(
            select(FetchRecord).where(
                FetchRecord.subreddit == subreddit.lower(),
                FetchRecord.fetched_from == from_dt,
                FetchRecord.fetched_to == to_dt,
            )
        )
        return result.scalar_one_or_none() is not None

    async def record(
        self,
        subreddit: str,
        from_dt: datetime,
        to_dt: datetime,
        post_count: int,
        comment_count: int,
        fetched_at: datetime,
    ) -> None:
        record = FetchRecord(
            subreddit=subreddit.lower(),
            fetched_from=from_dt,
            fetched_to=to_dt,
            post_count=post_count,
            comment_count=comment_count,
            fetched_at=fetched_at,
        )
        self._session.add(record)
        await self._session.commit()
