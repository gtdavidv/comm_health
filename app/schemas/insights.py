from datetime import date, datetime

from pydantic import BaseModel, Field


class TopContributor(BaseModel):
    username: str
    comment_count: int
    post_count: int
    total_contributions: int


class Alert(BaseModel):
    code: str
    severity: str  # "warning" | "critical"
    message: str
    value: float
    threshold: float


class CommunityHealthResponse(BaseModel):
    subreddit: str
    from_date: date
    to_date: date
    total_posts: int
    total_comments: int
    unique_contributors: int
    avg_comments_per_post: float
    median_response_time_minutes: float | None = Field(
        None,
        description="Median minutes from post creation to first captured comment. None if no commented posts.",
    )
    engagement_concentration_pct: float = Field(
        description="Percentage of comments authored by the top 5 users."
    )
    unanswered_post_rate_pct: float = Field(
        description="Percentage of posts with zero captured comments."
    )
    top_contributors: list[TopContributor]
    alerts: list[Alert]
    computed_at: datetime
