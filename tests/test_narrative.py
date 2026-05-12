"""Tests for narrative grounding — verifies LLM is not given raw data."""
import json
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.schemas.insights import CommunityHealthResponse
from app.services.narrative_service import _format_metrics, generate_narrative


def make_sample_metrics() -> CommunityHealthResponse:
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


class TestMetricsFormatting:
    def test_formatted_output_contains_aggregated_metrics(self):
        metrics = make_sample_metrics()
        formatted = _format_metrics(metrics)

        assert "342" in formatted          # total_posts
        assert "4821" in formatted         # total_comments
        assert "892" in formatted          # unique_contributors
        assert "18.3" in formatted         # concentration
        assert "23.5" in formatted         # response time

    def test_formatted_output_has_no_raw_reddit_content(self):
        """The LLM prompt must NOT include raw post titles or comment bodies."""
        metrics = make_sample_metrics()
        formatted = _format_metrics(metrics)

        # These markers would indicate raw content is leaking through
        assert "selftext" not in formatted
        assert "link_id" not in formatted
        assert "t3_" not in formatted

    def test_alert_included_when_present(self):
        from app.schemas.insights import Alert
        metrics = make_sample_metrics()
        metrics.alerts = [
            Alert(
                code="HIGH_CONCENTRATION",
                severity="warning",
                message="Top 5 users account for 45.0% of comments.",
                value=45.0,
                threshold=40.0,
            )
        ]
        formatted = _format_metrics(metrics)
        assert "HIGH_CONCENTRATION" in formatted


class TestGenerateNarrative:
    @pytest.mark.asyncio
    async def test_successful_narrative_generation(self):
        metrics = make_sample_metrics()
        mock_response = json.dumps({
            "community_type": "niche expert community",
            "narrative": "r/LocalLLaMA shows the signature of a high-signal expert community.",
            "confidence": 0.92,
            "evidence": [
                {"metric": "total_posts", "value": 342, "interpretation": "High activity"},
                {"metric": "engagement_concentration_pct", "value": 18.3, "interpretation": "Diverse"},
            ],
        })

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value=mock_response)

        result = await generate_narrative(metrics, mock_provider)

        assert result.subreddit == "LocalLLaMA"
        assert result.community_type == "niche expert community"
        assert result.confidence == pytest.approx(0.92)
        assert len(result.evidence) == 2
        assert result.evidence[0].metric == "total_posts"

    @pytest.mark.asyncio
    async def test_provider_receives_metrics_not_raw_data(self):
        """Verify the prompt passed to the LLM contains metrics, not raw Reddit API data."""
        metrics = make_sample_metrics()
        mock_response = json.dumps({
            "community_type": "debate community",
            "narrative": "Test narrative.",
            "confidence": 0.8,
            "evidence": [{"metric": "total_posts", "value": 342, "interpretation": "x"}],
        })

        captured_user_prompt: list[str] = []

        async def capture_generate(system: str, user: str) -> str:
            captured_user_prompt.append(user)
            return mock_response

        mock_provider = AsyncMock()
        mock_provider.generate = capture_generate

        await generate_narrative(metrics, mock_provider)

        assert captured_user_prompt, "generate was not called"
        prompt = captured_user_prompt[0]

        # Aggregated metrics are present
        assert "342" in prompt
        assert "4821" in prompt

        # Raw Reddit API fields are absent
        assert "selftext" not in prompt
        assert "link_id" not in prompt
        assert "body" not in prompt.lower()

    @pytest.mark.asyncio
    async def test_invalid_json_raises_value_error(self):
        metrics = make_sample_metrics()

        mock_provider = AsyncMock()
        mock_provider.generate = AsyncMock(return_value="not valid json {{{")

        with pytest.raises(ValueError, match="invalid JSON"):
            await generate_narrative(metrics, mock_provider)
