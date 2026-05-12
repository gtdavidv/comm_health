import json
from datetime import date

import structlog

from app.llm.base import LLMProvider
from app.schemas.insights import CommunityHealthResponse
from app.schemas.narrative import EvidenceItem, NarrativeSummaryResponse

log = structlog.get_logger(__name__)

SYSTEM_PROMPT = """\
You are a community analytics analyst. You will receive pre-computed metrics about a Reddit community.

Your job is to diagnose what kind of community this is based on the shape of the data, and explain \
what that means in practice — how it functions, who it serves, and where its natural strengths and \
weaknesses lie. This is an insight, not a summary. Do not restate the numbers; use them to say \
something true about the community that the numbers alone do not say.

Community types to consider (not exhaustive): broadcast, debate, support, niche expert, news \
aggregator, casual social. A community may combine traits — be specific.

Your task:
1. Classify the community into a type (a short label, e.g. "niche expert community").
2. Write an insightful narrative (3-5 sentences) that explains what that classification means \
for this specific community — its character, how engagement works, and what the data suggests \
about its strengths or fragility.
3. Assign a confidence score (0.0–1.0) reflecting data richness:
   - ≥0.90 → 200+ posts and 1000+ comments
   - 0.70–0.89 → 50–199 posts
   - 0.50–0.69 → 10–49 posts
   - <0.50 → fewer than 10 posts
4. Provide an evidence array (3–5 items) where each item cites a specific metric value that \
supports your characterisation.

Rules:
- Reference ONLY the metrics provided. Do not invent numbers or trends.
- Every evidence item must include the exact metric name and its numeric value from the input.
- Do not reference raw Reddit posts or comments; only the aggregated metrics below.

Respond ONLY with valid JSON matching this schema:
{
  "community_type": "<short label>",
  "narrative": "<string>",
  "confidence": <float 0.0-1.0>,
  "evidence": [
    {"metric": "<string>", "value": <number or string>, "interpretation": "<string>"},
    ...
  ]
}
"""


def _format_metrics(metrics: CommunityHealthResponse) -> str:
    alert_lines = "\n".join(
        f"  - [{a.severity.upper()}] {a.code}: {a.message}" for a in metrics.alerts
    ) or "  (none)"

    top_contrib = "\n".join(
        f"  {i + 1}. {c.username}: {c.comment_count} comments, {c.post_count} posts"
        for i, c in enumerate(metrics.top_contributors[:5])
    ) or "  (no contributors)"

    rt = (
        f"{metrics.median_response_time_minutes:.1f} minutes"
        if metrics.median_response_time_minutes is not None
        else "N/A (no commented posts)"
    )

    return f"""\
COMMUNITY HEALTH METRICS
========================
Subreddit: r/{metrics.subreddit}
Period: {metrics.from_date} to {metrics.to_date}

VOLUME:
  total_posts: {metrics.total_posts}
  total_comments: {metrics.total_comments}
  unique_contributors: {metrics.unique_contributors}

ENGAGEMENT:
  avg_comments_per_post: {metrics.avg_comments_per_post}
  median_response_time: {rt}
  engagement_concentration_pct: {metrics.engagement_concentration_pct}%
  unanswered_post_rate_pct: {metrics.unanswered_post_rate_pct}%

TOP CONTRIBUTORS:
{top_contrib}

ALERTS:
{alert_lines}
"""


async def generate_narrative(
    metrics: CommunityHealthResponse,
    provider: LLMProvider,
) -> NarrativeSummaryResponse:
    user_prompt = _format_metrics(metrics)
    log.info("narrative_request", subreddit=metrics.subreddit)

    raw = await provider.generate(system=SYSTEM_PROMPT, user=user_prompt)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("narrative_json_parse_error", raw=raw[:300], error=str(exc))
        raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

    evidence = [
        EvidenceItem(
            metric=item.get("metric", ""),
            value=item["value"],
            interpretation=item.get("interpretation", ""),
        )
        for item in parsed.get("evidence", [])
        if "value" in item
    ]

    return NarrativeSummaryResponse(
        subreddit=metrics.subreddit,
        from_date=metrics.from_date,
        to_date=metrics.to_date,
        community_type=parsed.get("community_type", ""),
        narrative=parsed.get("narrative", ""),
        confidence=float(parsed.get("confidence", 0.5)),
        evidence=evidence,
    )
