from datetime import datetime
from typing import Dict, List

from pydantic import BaseModel, Field, field_validator


class SenateContextElement(BaseModel):
    topic: str | None = Field(None, description="Topic discussed in the session")
    aspects: str | None = Field(None, description="Aspects discussed in the session")
    agreements: str | None = Field(
        None, description="Agreements achieved in the session"
    )


class ChamberOfDeputiesContextElement(BaseModel):
    citation: str | None = Field(None, description="Topic to discuss in the session")
    results: str | None = Field(None, description="Results for the citation")


class SenateAttendanceElement(BaseModel):
    members: List[str] | None = Field(None, description="Senators in the session")
    guests: List[str] | None = Field(None, description="Guests invited to the session")


class ChamberOfDeputiesAttendanceElement(BaseModel):
    name: str | None = Field(None, description="Name of the deputy")
    status: str | None = Field(
        None, description="Whether the deputy was present or not"
    )


class ExtractRequest(BaseModel):
    start: str | None = Field(
        None, description="Start date in YYYY-MM-DD format", example="2024-01-01"
    )
    finish: str | None = Field(
        None, description="End date in YYYY-MM-DD format", example="2024-12-31"
    )

    @field_validator("start", "finish")
    def validate_date_format(cls, v: str | None):
        if v is not None:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError("Date must be in YYYY-MM-DD format")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {"start": "2024-01-01", "finish": "2024-12-31"}
        }
    }


class TranscriptRequest(BaseModel):
    id: int = Field(..., description="Session ID", example="12345")
    commission_id: int = Field(..., description="Commission ID", example="3309")
    start: datetime = Field(
        ...,
        description="Date and time of session's beginning",
        example="2025-01-01T00:00:00.000+00:00",
    )
    finish: datetime = Field(
        ...,
        description="Date and time of session's end",
        example="2025-01-01T00:00:00.000+00:00",
    )
    context: List[SenateContextElement | ChamberOfDeputiesContextElement] = Field(
        ..., description="Session's context"
    )
    attendance: SenateAttendanceElement | List[ChamberOfDeputiesAttendanceElement] = (
        Field(..., description="Session's attendance")
    )


class QueryRequest(BaseModel):
    message: str = Field(..., description="Query to process")
    filters: Dict = Field(..., description="Filters to apply")


class ToggleFlag(BaseModel):
    enabled: bool
