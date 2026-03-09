"""Optional LLM enrichment for patient summaries and ranked hypotheses."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_SECONDS = 1.5
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE_URL = "https://api.openai.com/v1"


def enrich_case_summary(patient_summary: str, hypotheses: list[dict], *, ai_options: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return optional LLM-generated narrative for the patient case."""
    settings = ai_options or {}
    base_url = str(settings.get("base_url") or os.getenv("OPENAI_BASE_URL", DEFAULT_BASE_URL)).strip().rstrip("/")
    model = str(settings.get("model") or os.getenv("OPENAI_MODEL", DEFAULT_MODEL)).strip() or DEFAULT_MODEL
    api_key = str(settings.get("api_key") or os.getenv("OPENAI_API_KEY", "")).strip()

    if not _can_call_llm(base_url, api_key):
        return {
            "enabled": True,
            "status": "skipped",
            "reason": "missing_credentials",
            "model": model,
            "base_url": base_url,
            "patient_summary": patient_summary,
        }

    prompt = (
        "You are helping explain a biomedical hypothesis ranking for a clinician-facing research assistant. "
        "Return strict JSON with keys patient_summary and top_hypothesis_summary. "
        "Keep each value to one sentence.\n\n"
        f"PATIENT: {patient_summary}\n"
        f"HYPOTHESES: {json.dumps(hypotheses[:3], ensure_ascii=True)}"
    )
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 220,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    raw = _call_with_retry(f"{base_url}/chat/completions", headers, payload)
    parsed = _parse_object(raw)
    if not parsed:
        return {
            "enabled": True,
            "status": "error",
            "model": model,
            "base_url": base_url,
            "detail": "Unable to parse model output",
            "patient_summary": patient_summary,
        }

    return {
        "enabled": True,
        "status": "completed",
        "model": model,
        "base_url": base_url,
        "patient_summary": parsed.get("patient_summary", patient_summary),
        "top_hypothesis_summary": parsed.get("top_hypothesis_summary", ""),
    }


def _call_with_retry(url: str, headers: dict[str, str], payload: dict) -> str:
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=45)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            if attempt >= MAX_RETRIES - 1:
                logger.warning("LLM request failed after retries: %s", exc)
                return ""
            time.sleep(BACKOFF_SECONDS ** (attempt + 1))
    return ""


def _parse_object(text: str) -> dict[str, str]:
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return {str(key): str(value).strip() for key, value in parsed.items()}
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(key): str(value).strip() for key, value in parsed.items()}


def _can_call_llm(base_url: str, api_key: str) -> bool:
    if api_key:
        return True
    return "localhost" in base_url or "127.0.0.1" in base_url
