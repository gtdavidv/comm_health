"""Tests for metrics computation (pure functions, no DB or network)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.reddit import Comment, Post
from app.services.metrics_service import (
    _engagement_concentration,
    _response_times_minutes,
    _unique_contributors,
    compute_health,
)

UTC = timezone.utc
BASE_TIME = datetime(2026, 4, 10, 12, 0, 0, tzinfo=UTC)
FROM_DT = datetime(2026, 4, 1, tzinfo=UTC)
TO_DT = datetime(2026, 4, 30, 23, 59, 59, tzinfo=UTC)


def make_post(reddit_id: str, author: str = "alice", offset_hours: int = 0) -> Post:
    p = Post()
    p.reddit_id = reddit_id
    p.subreddit = "test"
    p.title = "Test post"
    p.author = author
    p.score = 10
    p.num_comments = 1
    p.created_utc = BASE_TIME + timedelta(hours=offset_hours)
    p.fetched_at = BASE_TIME
    return p


def make_comment(
    reddit_id: str,
    post_reddit_id: str,
    author: str = "bob",
    offset_minutes: int = 10,
) -> Comment:
    c = Comment()
    c.reddit_id = reddit_id
    c.post_reddit_id = post_reddit_id
    c.subreddit = "test"
    c.author = author
    c.body = "A comment"
    c.score = 5
    c.created_utc = BASE_TIME + timedelta(minutes=offset_minutes)
    c.fetched_at = BASE_TIME
    return c


class TestUniqueContributors:
    def test_counts_distinct_authors(self):
        posts = [make_post("p1", "alice"), make_post("p2", "bob")]
        comments = [make_comment("c1", "p1", "alice"), make_comment("c2", "p1", "carol")]
        assert _unique_contributors(posts, comments) == 3  # alice, bob, carol

    def test_deduplicates_same_author(self):
        posts = [make_post("p1", "alice")]
        comments = [make_comment("c1", "p1", "alice")]
        assert _unique_contributors(posts, comments) == 1

    def test_excludes_deleted(self):
        posts = [make_post("p1", "[deleted]")]
        comments = [make_comment("c1", "p1", "[deleted]")]
        assert _unique_contributors(posts, comments) == 0


class TestResponseTimes:
    def test_basic_response_time(self):
        post = make_post("p1", offset_hours=0)  # BASE_TIME
        comment = make_comment("c1", "p1", offset_minutes=30)  # BASE_TIME + 30min
        comment.created_utc = BASE_TIME + timedelta(minutes=30)

        times = _response_times_minutes([post], [comment])
        assert len(times) == 1
        assert times[0] == pytest.approx(30.0)

    def test_no_comments_returns_empty(self):
        post = make_post("p1")
        assert _response_times_minutes([post], []) == []

    def test_uses_earliest_comment_per_post(self):
        post = make_post("p1", offset_hours=0)
        c1 = make_comment("c1", "p1", offset_minutes=60)
        c2 = make_comment("c2", "p1", offset_minutes=20)
        c1.created_utc = BASE_TIME + timedelta(minutes=60)
        c2.created_utc = BASE_TIME + timedelta(minutes=20)

        times = _response_times_minutes([post], [c1, c2])
        assert len(times) == 1
        assert times[0] == pytest.approx(20.0)


class TestEngagementConcentration:
    def test_single_user_all_comments(self):
        comments = [make_comment(f"c{i}", "p1", "alice") for i in range(10)]
        conc = _engagement_concentration(comments, top_n=5)
        assert conc == pytest.approx(100.0)

    def test_even_distribution(self):
        comments = [make_comment(f"c{i}", "p1", f"user{i}") for i in range(10)]
        conc = _engagement_concentration(comments, top_n=5)
        assert conc == pytest.approx(50.0)

    def test_empty_returns_zero(self):
        assert _engagement_concentration([], top_n=5) == 0.0


class TestComputeHealth:
    def test_basic_metrics(self):
        posts = [make_post("p1"), make_post("p2")]
        c1 = make_comment("c1", "p1")
        c1.created_utc = BASE_TIME + timedelta(minutes=15)
        c2 = make_comment("c2", "p1")
        c2.created_utc = BASE_TIME + timedelta(minutes=45)

        result = compute_health("test", FROM_DT, TO_DT, posts, [c1, c2])

        assert result.total_posts == 2
        assert result.total_comments == 2
        assert result.avg_comments_per_post == 1.0
        assert result.unanswered_post_rate_pct == 50.0  # p2 has no comments

    def test_empty_data(self):
        result = compute_health("test", FROM_DT, TO_DT, [], [])
        assert result.total_posts == 0
        assert result.total_comments == 0
        assert result.unique_contributors == 0
        assert result.avg_comments_per_post == 0.0
        assert result.median_response_time_minutes is None
