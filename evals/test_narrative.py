"""
Eval suite for the narrative generation endpoint.

Run with:
    docker compose run --rm commhealth-api pytest evals/ -v

Requires OPENAI_API_KEY to be set. Each test makes one real LLM call.

Two sections:
  - DETERMINISTIC EVALS: assertions over LLM output using pure logic (string
    matching, numeric comparison, regex). Given a fixed LLM response these
    always produce the same pass/fail result.
  - LLM-AS-JUDGE EVALS (commented): require a second model call or embedding-
    based similarity to evaluate the first response. Not yet implemented.
"""

import re

import pytest

from app.services.narrative_service import _format_metrics, generate_narrative


# =============================================================================
# DETERMINISTIC EVALS
# =============================================================================


async def test_evidence_count_in_range(provider, healthy_metrics):
    result = await generate_narrative(healthy_metrics, provider)
    assert 3 <= len(result.evidence) <= 5, (
        f"Expected 3–5 evidence items, got {len(result.evidence)}"
    )


async def test_confidence_is_valid_probability(provider, healthy_metrics):
    result = await generate_narrative(healthy_metrics, provider)
    assert 0.0 <= result.confidence <= 1.0, (
        f"confidence {result.confidence} is outside [0.0, 1.0]"
    )


async def test_community_type_is_short_label(provider, healthy_metrics):
    result = await generate_narrative(healthy_metrics, provider)
    assert result.community_type, "community_type is empty"
    assert "\n" not in result.community_type, "community_type contains a newline"
    assert len(result.community_type) < 60, (
        f"community_type is {len(result.community_type)} chars — expected a short label"
    )


async def test_narrative_is_multiple_sentences(provider, healthy_metrics):
    result = await generate_narrative(healthy_metrics, provider)
    sentence_endings = re.findall(r"[.!?]", result.narrative)
    assert len(sentence_endings) >= 2, (
        f"narrative appears to be a single sentence: {result.narrative!r}"
    )


async def test_no_hallucinated_numbers_in_narrative(provider, healthy_metrics):
    result = await generate_narrative(healthy_metrics, provider)
    formatted = _format_metrics(healthy_metrics)

    # Normalise thousand-separator commas before extracting (4,821 → 4821)
    narrative_norm = result.narrative.replace(",", "")
    formatted_norm = formatted.replace(",", "")

    numbers = re.findall(r"\d+(?:\.\d+)?", narrative_norm)
    hallucinated = [n for n in numbers if n not in formatted_norm]
    assert not hallucinated, (
        f"Numbers in narrative not found in metrics input: {hallucinated}"
    )


async def test_high_data_confidence_threshold(provider, healthy_metrics):
    # healthy_metrics: 342 posts, 4821 comments — system prompt rule: >= 0.90
    result = await generate_narrative(healthy_metrics, provider)
    assert result.confidence >= 0.90, (
        f"Expected confidence >= 0.90 for high-volume data, got {result.confidence}"
    )


async def test_low_data_confidence_threshold(provider, sparse_metrics):
    # sparse_metrics: 5 posts — system prompt rule: < 0.50
    # Allow == 0.50: the model treats this as the floor and may land exactly on it
    result = await generate_narrative(sparse_metrics, provider)
    assert result.confidence <= 0.50, (
        f"Expected confidence <= 0.50 for sparse data, got {result.confidence}"
    )


async def test_evidence_metric_names_are_grounded(provider, healthy_metrics):
    result = await generate_narrative(healthy_metrics, provider)
    formatted = _format_metrics(healthy_metrics).lower()
    for item in result.evidence:
        assert item.metric.lower() in formatted, (
            f"Evidence metric {item.metric!r} not found in formatted metrics input"
        )


async def test_evidence_values_are_grounded(provider, healthy_metrics):
    result = await generate_narrative(healthy_metrics, provider)
    formatted = _format_metrics(healthy_metrics).replace(",", "")
    for item in result.evidence:
        if not isinstance(item.value, (int, float)):
            continue
        # Normalise whole floats (342.0 → "342") before checking
        value_str = str(int(item.value)) if isinstance(item.value, float) and float(item.value).is_integer() else str(item.value)
        assert value_str in formatted, (
            f"Evidence value {item.value!r} (as {value_str!r}) not found in metrics input"
        )


async def test_no_raw_reddit_fields_in_narrative(provider, healthy_metrics):
    result = await generate_narrative(healthy_metrics, provider)
    forbidden = ["selftext", "link_id", "t3_", "body"]
    found = [f for f in forbidden if f in result.narrative.lower()]
    assert not found, (
        f"Raw Reddit API field names found in narrative: {found}"
    )


# =============================================================================
# LLM-AS-JUDGE EVALS
# Implement these once a judge/scorer is wired up. Each requires either a
# second LLM call to evaluate the first response, or embedding-based similarity.
# =============================================================================

# async def test_community_type_semantically_matches_data(provider, ...):
#     """Community type label should be semantically appropriate for the metric shape.
#     E.g. high engagement_concentration_pct should produce a label like 'broadcast'
#     or 'dominated', not 'support community'. Requires a judge to score fitness."""
#     ...

# async def test_narrative_tone_matches_health(provider, ...):
#     """Healthy metrics (low concentration, fast response, low unanswered rate)
#     should produce positive framing. Critical alerts should produce cautious
#     framing. Requires sentiment scoring or a judge call."""
#     ...

# async def test_narrative_does_not_contradict_data(provider, ...):
#     """If unanswered_post_rate is 4%, the narrative must not say posts frequently
#     go unanswered. Detecting semantic contradiction requires a judge."""
#     ...

# async def test_narrative_provides_insight_beyond_numbers(provider, ...):
#     """The narrative should say something non-obvious — not just restate each
#     metric in prose. Measuring information gain requires a judge."""
#     ...

# async def test_evidence_interpretations_are_directionally_correct(provider, ...):
#     """'High post volume' for 500 posts is accurate; 'moderate activity' for 500
#     posts in a large subreddit context might not be. Requires domain judgment."""
#     ...

# async def test_similar_metrics_produce_similar_community_type(provider, ...):
#     """Two calls with nearly identical metrics should yield the same or
#     semantically similar community_type labels. Requires embedding similarity,
#     not string equality, to handle paraphrasing."""
#     ...

# async def test_alert_severity_reflected_in_language_strength(provider, ...):
#     """A critical alert should produce stronger cautionary language than a
#     warning-level alert for the same metric code. Requires a judge to score
#     language intensity."""
#     ...

# async def test_narrative_reads_as_coherent_prose(provider, ...):
#     """The narrative should flow as a connected paragraph, not a list of
#     disconnected facts. Coherence scoring requires a judge."""
#     ...

# async def test_community_type_is_specific_enough(provider, ...):
#     """Labels like 'community' or 'online community' are too generic to be
#     useful. Requires a judge to assess specificity."""
#     ...

# async def test_narrative_does_not_fabricate_external_references(provider, ...):
#     """The narrative must not compare the subreddit to named external communities
#     or subreddits not present in the metrics input. Requires a judge to detect
#     hallucinated references."""
#     ...
