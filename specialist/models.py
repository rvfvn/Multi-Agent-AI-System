from typing import Literal

from pydantic import BaseModel, Field, field_validator


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


class SpecialistResult(BaseModel):
    category: str = Field(min_length=1)
    resolution: str = Field(min_length=1)
    sources: list[str] = Field(min_length=1)


class TaskResponse(BaseModel):
    task_id: str
    status: TaskStatus
    result: SpecialistResult | None = None
    error: str | None = None