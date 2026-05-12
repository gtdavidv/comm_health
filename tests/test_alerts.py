"""Tests for alert rule generation."""
from datetime import datetime, timedelta, timezone

import pytest

from app.models.reddit import Comment, Post
from app.services.metrics_service import (
    CONCENTRATION_CRITICAL_PCT,
    CONCENTRATION_WARNING_PCT,
    UNANSWERED_CRITICAL_PCT,
    UNANSWERED_WARNING_PCT,
    _generate_alerts,
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
    p.title = "post"
    p.author = author
    p.score = 1
    p.num_comments = 0
    p.created_utc = BASE_TIME + timedelta(hours=offset_hours)
    p.fetched_at = BASE_TIME
    return p


def make_comment(reddit_id: str, post_reddit_id: str, author: str = "bob", offset_minutes: int = 10) -> Comment:
    c = Comment()
    c.reddit_id = reddit_id
    c.post_reddit_id = post_reddit_id
    c.subreddit = "test"
    c.author = author
    c.body = "x"
    c.score = 1
    c.created_utc = BASE_TIME + timedelta(minutes=offset_minutes)
    c.fetched_at = BASE_TIME
    return c


class TestHighConcentrationAlert:
    def test_no_alert_below_threshold(self):
        # 10 comments spread across 10 users — 5 users = 50% > warning threshold
        # Let's create 20 unique users
        comments = [make_comment(f"c{i}", "p1", f"user{i}") for i in range(20)]
        alerts = _generate_alerts(
            engagement_concentration=15.0,
            unanswered_rate=0.0,
            posts=[make_post("p1")],
            relevant_comments=comments,
        )
        assert not any(a.code == "HIGH_CONCENTRATION" for a in alerts)

    def test_warning_at_warning_threshold(self):
        alerts = _generate_alerts(
            engagement_concentration=CONCENTRATION_WARNING_PCT,
            unanswered_rate=0.0,
            posts=[make_post("p1")],
            relevant_comments=[make_comment("c1", "p1")],
        )
        conc_alerts = [a for a in alerts if a.code == "HIGH_CONCENTRATION"]
        assert len(conc_alerts) == 1
        assert conc_alerts[0].severity == "warning"

    def test_critical_above_critical_threshold(self):
        alerts = _generate_alerts(
            engagement_concentration=CONCENTRATION_CRITICAL_PCT + 1,
            unanswered_rate=0.0,
            posts=[make_post("p1")],
            relevant_comments=[make_comment("c1", "p1")],
        )
        conc_alerts = [a for a in alerts if a.code == "HIGH_CONCENTRATION"]
        assert len(conc_alerts) == 1
        assert conc_alerts[0].severity == "critical"


class TestUnansweredPostRateAlert:
    def test_no_alert_below_threshold(self):
        alerts = _generate_alerts(
            engagement_concentration=0.0,
            unanswered_rate=10.0,
            posts=[make_post("p1")],
            relevant_comments=[],
        )
        assert not any(a.code == "HIGH_UNANSWERED_POST_RATE" for a in alerts)

    def test_warning_at_warning_threshold(self):
        alerts = _generate_alerts(
            engagement_concentration=0.0,
            unanswered_rate=UNANSWERED_WARNING_PCT,
            posts=[make_post("p1")],
            relevant_comments=[],
        )
        ua = [a for a in alerts if a.code == "HIGH_UNANSWERED_POST_RATE"]
        assert len(ua) == 1
        assert ua[0].severity == "warning"

    def test_critical_at_critical_threshold(self):
        alerts = _generate_alerts(
            engagement_concentration=0.0,
            unanswered_rate=UNANSWERED_CRITICAL_PCT,
            posts=[make_post("p1")],
            relevant_comments=[],
        )
        ua = [a for a in alerts if a.code == "HIGH_UNANSWERED_POST_RATE"]
        assert ua[0].severity == "critical"


class TestResponseTimeIncreaseAlert:
    def _make_posts_and_comments_with_trend(
        self, first_half_rt: int, second_half_rt: int, n: int = 10
    ) -> tuple[list[Post], list[Comment]]:
        """Create n posts in each half with specified response times (minutes)."""
        posts: list[Post] = []
        comments: list[Comment] = []

        for i in range(n):
            # First half: posts spread over first 15 days
            p = make_post(f"p1_{i}", offset_hours=i * 24)
            posts.append(p)
            c = make_comment(f"c1_{i}", f"p1_{i}", offset_minutes=0)
            c.created_utc = p.created_utc + timedelta(minutes=first_half_rt)
            comments.append(c)

        for i in range(n):
            # Second half: posts spread over next 15 days
            p = make_post(f"p2_{i}", offset_hours=(n + i) * 24)
            posts.append(p)
            c = make_comment(f"c2_{i}", f"p2_{i}", offset_minutes=0)
            c.created_utc = p.created_utc + timedelta(minutes=second_half_rt)
            comments.append(c)

        return posts, comments

    def test_no_alert_stable_response_time(self):
        posts, comments = self._make_posts_and_comments_with_trend(30, 35)
        result = compute_health("test", FROM_DT, TO_DT, posts, comments)
        assert not any(a.code == "RESPONSE_TIME_INCREASE" for a in result.alerts)

    def test_alert_when_response_time_doubles(self):
        posts, comments = self._make_posts_and_comments_with_trend(30, 90)
        result = compute_health("test", FROM_DT, TO_DT, posts, comments)
        rt_alerts = [a for a in result.alerts if a.code == "RESPONSE_TIME_INCREASE"]
        assert len(rt_alerts) == 1

    def test_no_alert_insufficient_sample(self):
        # Only 3 posts per half — below RESPONSE_TIME_MIN_SAMPLE=5
        posts, comments = self._make_posts_and_comments_with_trend(30, 90, n=3)
        result = compute_health("test", FROM_DT, TO_DT, posts, comments)
        assert not any(a.code == "RESPONSE_TIME_INCREASE" for a in result.alerts)
