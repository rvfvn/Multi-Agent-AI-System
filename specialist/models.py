from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

CATEGORIES = {
    "account access": "Account Access",
    "network": "Network",
    "hardware": "Hardware",
    "software": "Software",
    "email": "Email",
    "security": "Security",
}


TaskStatus = Literal[
    "submitted",
    "working",
    "completed",
    "failed",
]


class TaskRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=2000,
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Question cannot be empty.")

        return value


class LLMAnswer(BaseModel):
    """Raw generation: unsupported answers may contain empty values."""

    model_config = ConfigDict(strict=True, extra="forbid")

    supported: bool
    category: str
    resolution: str
    sources: list[str]


class SpecialistResult(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    category: str = Field(min_length=1)
    resolution: str = Field(min_length=1)
    sources: list[str] = Field(min_length=1)

    @field_validator("category")
    @classmethod
    def validate_category(cls, value: str) -> str:
        category = CATEGORIES.get(value.strip().lower())
        if category is None:
            raise ValueError("Unknown Specialist category.")
        return category

    @field_validator("resolution")
    @classmethod
    def validate_resolution(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Resolution must not be blank.")
        return value

    @field_validator("sources")
    @classmethod
    def validate_sources(cls, values: list[str]) -> list[str]:
        sources = [value.strip() for value in values]
        if any(not source for source in sources):
            raise ValueError("Source references must not be blank.")
        return list(dict.fromkeys(sources))


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: SpecialistResult | None = None
    error: str | None = None
