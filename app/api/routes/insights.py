from datetime import date, datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.reddit import RedditAPIError
from app.db.session import get_db
from app.repositories.comment_repository import CommentRepository
from app.repositories.post_repository import PostRepository
from app.schemas.insights import CommunityHealthResponse
from app.services.ingestion_service import IngestionService
from app.services.metrics_service import compute_health

router = APIRouter(prefix="/api/insights", tags=["insights"])
log = structlog.get_logger(__name__)


@router.get(
    "/community-health",
    response_model=CommunityHealthResponse,
    summary="Community health metrics for a subreddit over a date range",
)
async def community_health(
    subreddit: str = Query(description="Subreddit name (without r/)"),
    from_date: date = Query(alias="from", description="Start date (ISO 8601, e.g. 2026-04-01)"),
    to_date: date = Query(alias="to", description="End date (ISO 8601, e.g. 2026-04-30)"),
    db: AsyncSession = Depends(get_db),
) -> CommunityHealthResponse:
    if from_date >= to_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="'from' must be before 'to'")
    if (to_date - from_date).days > 90:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Date range cannot exceed 90 days")

    from_dt = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    to_dt = datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    log.info("community_health_request", subreddit=subreddit, from_dt=from_dt, to_dt=to_dt)

    try:
        ingestion = IngestionService(db)
        await ingestion.ensure_data(subreddit, from_dt, to_dt)
    except RedditAPIError as exc:
        if exc.status_code == 404:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Subreddit '{subreddit}' not found") from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    posts = await PostRepository(db).get_in_range(subreddit, from_dt, to_dt)
    comments = await CommentRepository(db).get_for_posts(subreddit, [p.reddit_id for p in posts])

    return compute_health(subreddit, from_dt, to_dt, posts, comments)
