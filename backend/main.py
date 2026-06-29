"""
HealthSense AI backend — FastAPI application.

Endpoints:
  POST /api/symptom-check   -> analyze symptoms, return possible conditions + severity
  POST /api/medication-info -> educational medication information
  POST /api/triage          -> standalone severity/triage assessment
  GET  /api/health          -> health check
"""
from __future__ import annotations

import os
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from schemas import (
    SymptomCheckRequest,
    SymptomCheckResponse,
    PossibleCondition,
    MedicationInfoRequest,
    MedicationInfoResponse,
    TriageRequest,
    TriageResponse,
)
from claude_client import (
    call_claude_json,
    detect_emergency_keywords,
    SYMPTOM_SYSTEM_PROMPT,
    MEDICATION_SYSTEM_PROMPT,
    TRIAGE_SYSTEM_PROMPT,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("healthsense")

DISCLAIMER = (
    "HealthSense AI is an educational tool and does not provide medical diagnoses. "
    "It is not a substitute for professional medical advice, diagnosis, or treatment. "
    "Always seek the advice of a physician or other qualified health provider with any "
    "questions you may have regarding a medical condition. If you think you may have a "
    "medical emergency, call your local emergency number immediately."
)

EMERGENCY_NOTICE = (
    "EMERGENCY WARNING SIGNS DETECTED. This may be a medical emergency. "
    "Call your local emergency number (e.g. 911 in the US, 112 in the EU) or go to "
    "the nearest emergency room immediately. Do not wait."
)

app = FastAPI(
    title="HealthSense AI API",
    description="Educational symptom checker, medication info, and triage assistant.",
    version="1.0.0",
)

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin, "http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.post("/api/symptom-check", response_model=SymptomCheckResponse)
def symptom_check(payload: SymptomCheckRequest):
    if not payload.symptoms:
        raise HTTPException(status_code=400, detail="At least one symptom is required.")

    profile_lines = []
    if payload.age is not None:
        profile_lines.append(f"Age: {payload.age}")
    if payload.sex:
        profile_lines.append(f"Sex: {payload.sex}")
    if payload.existing_conditions:
        profile_lines.append(f"Existing conditions: {', '.join(payload.existing_conditions)}")
    if payload.current_medications:
        profile_lines.append(f"Current medications: {', '.join(payload.current_medications)}")
    if payload.duration:
        profile_lines.append(f"Duration of symptoms: {payload.duration}")

    user_content = (
        f"Symptoms reported: {', '.join(payload.symptoms)}\n"
        + ("\n".join(profile_lines) + "\n" if profile_lines else "")
        + (f"Additional notes: {payload.additional_notes}\n" if payload.additional_notes else "")
    )

    # Redundant client-side safety net for obvious emergency language
    combined_text = " ".join(payload.symptoms) + " " + (payload.additional_notes or "")
    keyword_flags = detect_emergency_keywords(combined_text)

    try:
        result = call_claude_json(SYMPTOM_SYSTEM_PROMPT, user_content)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Symptom check failed")
        raise HTTPException(status_code=502, detail=f"AI analysis failed: {exc}") from exc

    conditions = [PossibleCondition(**c) for c in result.get("possible_conditions", [])]

    severity_level = result.get("severity_level", "moderate")
    seek_emergency = bool(result.get("seek_emergency_care", False))
    red_flags = list(result.get("red_flags_detected", []))

    # If our keyword safety net found something the model missed, escalate.
    if keyword_flags and not seek_emergency:
        seek_emergency = True
        severity_level = "emergency"
        for kw in keyword_flags:
            if kw not in red_flags:
                red_flags.append(kw)

    general_guidance = result.get("general_guidance", "")
    if seek_emergency:
        general_guidance = f"{EMERGENCY_NOTICE} {general_guidance}".strip()

    return SymptomCheckResponse(
        possible_conditions=conditions,
        severity_level=severity_level,
        severity_explanation=result.get("severity_explanation", ""),
        recommended_action=result.get("recommended_action", ""),
        seek_emergency_care=seek_emergency,
        red_flags_detected=red_flags,
        general_guidance=general_guidance,
        disclaimer=DISCLAIMER,
    )


@app.post("/api/medication-info", response_model=MedicationInfoResponse)
def medication_info(payload: MedicationInfoRequest):
    user_content = f"Medication name: {payload.medication_name}"
    try:
        result = call_claude_json(MEDICATION_SYSTEM_PROMPT, user_content, max_tokens=1000)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Medication info failed")
        raise HTTPException(status_code=502, detail=f"AI lookup failed: {exc}") from exc

    return MedicationInfoResponse(
        name=result.get("name", payload.medication_name),
        drug_class=result.get("drug_class"),
        common_uses=result.get("common_uses", []),
        typical_administration=result.get("typical_administration"),
        common_side_effects=result.get("common_side_effects", []),
        serious_side_effects=result.get("serious_side_effects", []),
        interactions_to_be_aware_of=result.get("interactions_to_be_aware_of", []),
        important_notes=result.get("important_notes", []),
        disclaimer=DISCLAIMER,
    )


@app.post("/api/triage", response_model=TriageResponse)
def triage(payload: TriageRequest):
    keyword_flags = detect_emergency_keywords(payload.description)
    user_content = payload.description
    if payload.age is not None:
        user_content += f"\nAge: {payload.age}"

    try:
        result = call_claude_json(TRIAGE_SYSTEM_PROMPT, user_content, max_tokens=600)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Triage failed")
        raise HTTPException(status_code=502, detail=f"AI triage failed: {exc}") from exc

    severity_level = result.get("severity_level", "moderate")
    seek_emergency = bool(result.get("seek_emergency_care", False))
    explanation = result.get("explanation", "")

    if keyword_flags and not seek_emergency:
        seek_emergency = True
        severity_level = "emergency"
        explanation = f"{explanation} (Note: language matching emergency warning signs was detected.)".strip()

    return TriageResponse(
        severity_level=severity_level,
        explanation=explanation,
        seek_emergency_care=seek_emergency,
        recommended_action=result.get("recommended_action", ""),
        disclaimer=DISCLAIMER,
    )
