"""Pydantic schemas for Cure Graph API requests and responses."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


EvidenceMode = Literal["offline", "hybrid"]
Sex = Literal["female", "male", "other", "unknown"]


class AiSummaryOptions(BaseModel):
    """Optional LLM override values for AI summaries."""

    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None

    @field_validator("api_key", "base_url", "model")
    @classmethod
    def strip_optional_values(cls, value: str | None) -> str | None:
        """Normalize empty strings to None."""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PatientCase(BaseModel):
    """Structured patient case used to seed Cure Graph analysis."""

    patient_id: str = "demo-patient"
    age_range: str = Field("60-69", description="Age band, not exact DOB")
    sex: Sex = "unknown"
    diagnoses: list[str] = Field(default_factory=list)
    symptoms: list[str] = Field(default_factory=list)
    biomarkers: list[str] = Field(default_factory=list)
    medications: list[str] = Field(default_factory=list)

    @field_validator("patient_id", "age_range")
    @classmethod
    def validate_scalar_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    @field_validator("diagnoses", "symptoms", "biomarkers", "medications")
    @classmethod
    def normalize_terms(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item and item.strip()]
        deduped: list[str] = []
        seen: set[str] = set()
        for item in normalized:
            key = item.casefold()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped


class AnalyzeRequest(BaseModel):
    """Request payload for patient-case analysis."""

    patient_case: PatientCase
    report_text: str = ""
    evidence_mode: EvidenceMode = "hybrid"
    with_ai: bool = False
    ai: AiSummaryOptions | None = None

    @field_validator("report_text")
    @classmethod
    def normalize_report_text(cls, value: str) -> str:
        return value.strip()


class AnalyzeLocalRequest(AnalyzeRequest):
    """Backward-compatible alias for the primary analyze request."""
