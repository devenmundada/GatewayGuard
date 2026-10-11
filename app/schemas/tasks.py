"""
Pydantic schemas for tasks.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(None, max_length=10_000)


class TaskUpdate(BaseModel):
    """All fields optional: only the ones sent are changed."""
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=10_000)
    completed: bool | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str | None
    completed: bool
    created_at: datetime
    updated_at: datetime
