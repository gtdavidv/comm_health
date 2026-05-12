import os
from datetime import date, datetime, timezone

import pytest

from app.llm.openai_provider import OpenAIProvider
from app.schemas.insights import CommunityHealthResponse


@pytest.fixture(scope="module")
def provider():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        pytest.skip("OPENAI_API_KEY not set — skipping LLM evals")
    return OpenAIProvider(api_key=api_key, model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"))


@pytest.fixture
def healthy_metrics():
    """High-volume subreddit with healthy engagement. Should yield confidence >= 0.90."""
    return CommunityHealthResponse(
        subreddit="LocalLLaMA",
        from_date=date(2026, 4, 1),
        to_date=date(2026, 4, 30),
        total_posts=342,
        total_comments=4821,
        unique_contributors=892,
        avg_comments_per_post=14.09,
        median_response_time_minutes=23.5,
        engagement_concentration_pct=18.3,
        unanswered_post_rate_pct=8.2,
        top_contributors=[],
        alerts=[],
        computed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )


@pytest.fixture
def sparse_metrics():
    """Tiny subreddit with very few posts. Should yield confidence < 0.50."""
    return CommunityHealthResponse(
        subreddit="tinysubreddit",
        from_date=date(2026, 4, 1),
        to_date=date(2026, 4, 7),
        total_posts=5,
        total_comments=12,
        unique_contributors=8,
        avg_comments_per_post=2.4,
        median_response_time_minutes=45.0,
        engagement_concentration_pct=55.0,
        unanswered_post_rate_pct=20.0,
        top_contributors=[],
        alerts=[],
        computed_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
    )
