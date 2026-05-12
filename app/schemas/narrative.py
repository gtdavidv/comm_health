from datetime import date

from pydantic import BaseModel, Field, model_validator


class NarrativeRequest(BaseModel):
    subreddit: str = Field(min_length=1, max_length=50)
    from_date: date = Field(alias="from")
    to_date: date = Field(alias="to")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def validate_range(self) -> "NarrativeRequest":
        if self.from_date > self.to_date:
            raise ValueError("'from' must be before 'to'")
        delta = (self.to_date - self.from_date).days
        if delta > 90:
            raise ValueError("Date range cannot exceed 90 days")
        return self


class EvidenceItem(BaseModel):
    metric: str
    value: float | int | str
    interpretation: str


class NarrativeSummaryResponse(BaseModel):
    subreddit: str
    from_date: date
    to_date: date
    community_type: str
    narrative: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[EvidenceItem]
