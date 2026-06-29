"""
Pydantic models shared across the HealthSense AI backend.
"""
from __future__ import annotations

from typing import List, Optional, Literal
from pydantic import BaseModel, Field


# ---------- Symptom Checker ----------

class SymptomCheckRequest(BaseModel):
    symptoms: List[str] = Field(..., min_length=1, description="List of symptom descriptions")
    duration: Optional[str] = Field(None, description="How long symptoms have lasted, e.g. '3 days'")
    age: Optional[int] = Field(None, ge=0, le=120)
    sex: Optional[Literal["male", "female", "other", "prefer_not_to_say"]] = None
    existing_conditions: Optional[List[str]] = Field(default_factory=list)
    current_medications: Optional[List[str]] = Field(default_factory=list)
    additional_notes: Optional[str] = None


class PossibleCondition(BaseModel):
    name: str
    likelihood: Literal["low", "moderate", "high"]
    explanation: str


class SymptomCheckResponse(BaseModel):
    possible_conditions: List[PossibleCondition]
    severity_level: Literal["mild", "moderate", "severe", "emergency"]
    severity_explanation: str
    recommended_action: str
    seek_emergency_care: bool
    red_flags_detected: List[str] = Field(default_factory=list)
    general_guidance: str
    disclaimer: str


# ---------- Medication Info ----------

class MedicationInfoRequest(BaseModel):
    medication_name: str = Field(..., min_length=2)


class MedicationInfoResponse(BaseModel):
    name: str
    drug_class: Optional[str] = None
    common_uses: List[str] = Field(default_factory=list)
    typical_administration: Optional[str] = None
    common_side_effects: List[str] = Field(default_factory=list)
    serious_side_effects: List[str] = Field(default_factory=list)
    interactions_to_be_aware_of: List[str] = Field(default_factory=list)
    important_notes: List[str] = Field(default_factory=list)
    disclaimer: str


# ---------- Severity / Triage (standalone) ----------

class TriageRequest(BaseModel):
    description: str = Field(..., min_length=5, description="Free-text description of the situation")
    age: Optional[int] = None


class TriageResponse(BaseModel):
    severity_level: Literal["mild", "moderate", "severe", "emergency"]
    explanation: str
    seek_emergency_care: bool
    recommended_action: str
    disclaimer: str
