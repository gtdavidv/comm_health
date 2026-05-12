from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.reddit import RedditAPIError
from app.db.session import get_db
from app.llm.factory import create_provider
from app.repositories.comment_repository import CommentRepository
from app.repositories.post_repository import PostRepository
from app.schemas.narrative import NarrativeRequest, NarrativeSummaryResponse
from app.services.ingestion_service import IngestionService
from app.services.metrics_service import compute_health
from app.services.narrative_service import generate_narrative

router = APIRouter(prefix="/api/narrative", tags=["narrative"])
log = structlog.get_logger(__name__)


@router.post(
    "/community-summary",
    response_model=NarrativeSummaryResponse,
    summary="LLM-generated narrative summary grounded in computed metrics",
)
async def community_summary(
    request: NarrativeRequest,
    db: AsyncSession = Depends(get_db),
) -> NarrativeSummaryResponse:
    from_dt = datetime.combine(request.from_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    to_dt = datetime.combine(request.to_date, datetime.max.time()).replace(tzinfo=timezone.utc)

    log.info("narrative_request", subreddit=request.subreddit, from_dt=from_dt, to_dt=to_dt)

    try:
        ingestion = IngestionService(db)
        await ingestion.ensure_data(request.subreddit, from_dt, to_dt)
    except RedditAPIError as exc:
        if exc.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Subreddit r/{request.subreddit} not found",
            ) from exc
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.args[0]) from exc

    posts = await PostRepository(db).get_in_range(request.subreddit, from_dt, to_dt)
    comments = await CommentRepository(db).get_for_posts(
        request.subreddit, [p.reddit_id for p in posts]
    )
    metrics = compute_health(request.subreddit, from_dt, to_dt, posts, comments)

    try:
        provider = create_provider()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"LLM provider not configured: {exc}",
        ) from exc

    try:
        return await generate_narrative(metrics, provider)
    except ValueError as exc:
        log.error("narrative_generation_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM returned an unexpected response. Try again.",
        ) from exc
