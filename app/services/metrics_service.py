from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median

from app.models.reddit import Comment, Post
from app.schemas.insights import Alert, CommunityHealthResponse, TopContributor

# Alert thresholds
CONCENTRATION_WARNING_PCT = 40.0
CONCENTRATION_CRITICAL_PCT = 60.0
UNANSWERED_WARNING_PCT = 30.0
UNANSWERED_CRITICAL_PCT = 50.0
RESPONSE_TIME_INCREASE_FACTOR = 1.5
RESPONSE_TIME_MIN_SAMPLE = 5
TOP_N_CONTRIBUTORS = 5


def compute_health(
    subreddit: str,
    from_date: datetime,
    to_date: datetime,
    posts: list[Post],
    comments: list[Comment],
) -> CommunityHealthResponse:
    total_posts = len(posts)
    post_ids = {p.reddit_id for p in posts}

    # Comments that belong to posts in our range
    relevant_comments = [c for c in comments if c.post_reddit_id in post_ids]
    relevant_comment_count = len(relevant_comments)

    unique_contributors = _unique_contributors(posts, relevant_comments)
    avg_comments_per_post = relevant_comment_count / total_posts if total_posts else 0.0

    response_times = _response_times_minutes(posts, relevant_comments)
    median_response_time = median(response_times) if response_times else None

    non_deleted = [c for c in relevant_comments if c.author != "[deleted]"]
    engagement_concentration = _engagement_concentration(non_deleted, TOP_N_CONTRIBUTORS)

    post_comment_counts = Counter(c.post_reddit_id for c in relevant_comments)
    unanswered = sum(1 for p in posts if post_comment_counts[p.reddit_id] == 0)
    unanswered_rate = (unanswered / total_posts * 100) if total_posts else 0.0

    top_contributors = _top_contributors(posts, relevant_comments)

    alerts = _generate_alerts(
        engagement_concentration=engagement_concentration,
        unanswered_rate=unanswered_rate,
        posts=posts,
        relevant_comments=relevant_comments,
    )

    return CommunityHealthResponse(
        subreddit=subreddit,
        from_date=from_date.date(),
        to_date=to_date.date(),
        total_posts=total_posts,
        total_comments=relevant_comment_count,
        unique_contributors=unique_contributors,
        avg_comments_per_post=round(avg_comments_per_post, 2),
        median_response_time_minutes=round(median_response_time, 1) if median_response_time is not None else None,
        engagement_concentration_pct=round(engagement_concentration, 1),
        unanswered_post_rate_pct=round(unanswered_rate, 1),
        top_contributors=top_contributors,
        alerts=alerts,
        computed_at=datetime.now(tz=timezone.utc),
    )


def _unique_contributors(posts: list[Post], comments: list[Comment]) -> int:
    authors: set[str] = set()
    for p in posts:
        if p.author and p.author != "[deleted]":
            authors.add(p.author)
    for c in comments:
        if c.author and c.author != "[deleted]":
            authors.add(c.author)
    return len(authors)


def _response_times_minutes(posts: list[Post], comments: list[Comment]) -> list[float]:
    first_comment: dict[str, datetime] = {}
    for c in comments:
        prev = first_comment.get(c.post_reddit_id)
        if prev is None or c.created_utc < prev:
            first_comment[c.post_reddit_id] = c.created_utc

    times: list[float] = []
    for p in posts:
        fc = first_comment.get(p.reddit_id)
        if fc is None:
            continue
        delta = fc - p.created_utc
        if delta >= timedelta(0):
            times.append(delta.total_seconds() / 60)

    return times


def _engagement_concentration(comments: list[Comment], top_n: int) -> float:
    if not comments:
        return 0.0
    counts = Counter(c.author for c in comments)
    top_total = sum(count for _, count in counts.most_common(top_n))
    return top_total / len(comments) * 100


def _top_contributors(posts: list[Post], comments: list[Comment]) -> list[TopContributor]:
    comment_counts: Counter[str] = Counter()
    post_counts: Counter[str] = Counter()

    for p in posts:
        if p.author and p.author != "[deleted]":
            post_counts[p.author] += 1
    for c in comments:
        if c.author and c.author != "[deleted]":
            comment_counts[c.author] += 1

    all_authors = set(comment_counts) | set(post_counts)
    contributors = [
        TopContributor(
            username=author,
            comment_count=comment_counts[author],
            post_count=post_counts[author],
            total_contributions=comment_counts[author] + post_counts[author],
        )
        for author in all_authors
    ]
    contributors.sort(key=lambda x: x.total_contributions, reverse=True)
    return contributors[:10]


def _generate_alerts(
    engagement_concentration: float,
    unanswered_rate: float,
    posts: list[Post],
    relevant_comments: list[Comment],
) -> list[Alert]:
    alerts: list[Alert] = []

    # HIGH_CONCENTRATION
    if engagement_concentration >= CONCENTRATION_CRITICAL_PCT:
        alerts.append(Alert(
            code="HIGH_CONCENTRATION",
            severity="critical",
            message=(
                f"Top {TOP_N_CONTRIBUTORS} users account for "
                f"{engagement_concentration:.1f}% of comments."
            ),
            value=engagement_concentration,
            threshold=CONCENTRATION_CRITICAL_PCT,
        ))
    elif engagement_concentration >= CONCENTRATION_WARNING_PCT:
        alerts.append(Alert(
            code="HIGH_CONCENTRATION",
            severity="warning",
            message=(
                f"Top {TOP_N_CONTRIBUTORS} users account for "
                f"{engagement_concentration:.1f}% of comments."
            ),
            value=engagement_concentration,
            threshold=CONCENTRATION_WARNING_PCT,
        ))

    # HIGH_UNANSWERED_POST_RATE
    if unanswered_rate >= UNANSWERED_CRITICAL_PCT:
        alerts.append(Alert(
            code="HIGH_UNANSWERED_POST_RATE",
            severity="critical",
            message=f"{unanswered_rate:.1f}% of posts received no comments.",
            value=unanswered_rate,
            threshold=UNANSWERED_CRITICAL_PCT,
        ))
    elif unanswered_rate >= UNANSWERED_WARNING_PCT:
        alerts.append(Alert(
            code="HIGH_UNANSWERED_POST_RATE",
            severity="warning",
            message=f"{unanswered_rate:.1f}% of posts received no comments.",
            value=unanswered_rate,
            threshold=UNANSWERED_WARNING_PCT,
        ))

    # RESPONSE_TIME_INCREASE — compare first half vs second half of the period
    rt_alert = _check_response_time_increase(posts, relevant_comments)
    if rt_alert:
        alerts.append(rt_alert)

    return alerts


def _check_response_time_increase(
    posts: list[Post],
    comments: list[Comment],
) -> Alert | None:
    if not posts:
        return None

    times = sorted(p.created_utc for p in posts)
    midpoint = times[0] + (times[-1] - times[0]) / 2

    first_half = [p for p in posts if p.created_utc <= midpoint]
    second_half = [p for p in posts if p.created_utc > midpoint]

    if len(first_half) < RESPONSE_TIME_MIN_SAMPLE or len(second_half) < RESPONSE_TIME_MIN_SAMPLE:
        return None

    first_ids = {p.reddit_id for p in first_half}
    second_ids = {p.reddit_id for p in second_half}

    first_comments = [c for c in comments if c.post_reddit_id in first_ids]
    second_comments = [c for c in comments if c.post_reddit_id in second_ids]

    first_rt = _response_times_minutes(first_half, first_comments)
    second_rt = _response_times_minutes(second_half, second_comments)

    if len(first_rt) < RESPONSE_TIME_MIN_SAMPLE or len(second_rt) < RESPONSE_TIME_MIN_SAMPLE:
        return None

    first_median = median(first_rt)
    second_median = median(second_rt)

    if first_median == 0:
        return None

    ratio = second_median / first_median
    if ratio >= RESPONSE_TIME_INCREASE_FACTOR:
        severity = "critical" if ratio >= 2.0 else "warning"
        return Alert(
            code="RESPONSE_TIME_INCREASE",
            severity=severity,
            message=(
                f"Median response time increased {ratio:.1f}x "
                f"({first_median:.0f}m → {second_median:.0f}m) over the period."
            ),
            value=round(second_median, 1),
            threshold=round(first_median * RESPONSE_TIME_INCREASE_FACTOR, 1),
        )

    return None
