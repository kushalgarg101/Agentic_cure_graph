"""OpenFDA provider for Agentic Cure Graph.

Provides access to FDA drug labeling data via OpenFDA API.
https://api.fda.gov/
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import requests

from github_viz.providers import EvidenceProvider, ProviderMetadata

logger = logging.getLogger(__name__)

OPENFDA_BASE = "https://api.fda.gov/drug"


@dataclass
class OpenFDAProvider(EvidenceProvider):
    """OpenFDA evidence provider for drug labeling and safety data."""

    def __init__(self):
        self.session = requests.Session()

    def describe(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id="openfda",
            version="online",
            description="FDA drug labeling and safety data via OpenFDA API",
            kind="online_api",
            location="https://api.fda.gov/",
        )

    def load(self) -> dict[str, Any]:
        return self._fetch_drug_data()

    def search_drug(self, drug_name: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search for a drug in FDA database."""
        url = f"{OPENFDA_BASE}/label.json"
        params = {
            "search": f'openfda.generic_name:"{drug_name}" OR openfda.brand_name:"{drug_name}"',
            "limit": limit,
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(
                    {
                        "id": item.get("id"),
                        "brand_name": item.get("openfda", {}).get("brand_name", []),
                        "generic_name": item.get("openfda", {}).get("generic_name", []),
                        "manufacturer": item.get("openfda", {}).get(
                            "manufacturer_name", []
                        ),
                        "route": item.get("openfda", {}).get("route", []),
                        "indications": item.get("indications_and_usage", []),
                        "warnings": item.get("warnings", []),
                    }
                )
            return results
        except Exception as e:
            logger.warning("Failed to search drug '%s': %s", drug_name, e)
            return []

    def get_drug_interactions(self, drug_name: str) -> list[dict[str, Any]]:
        """Get drug interaction information."""
        url = f"{OPENFDA_BASE}/druginteractions.json"
        params = {
            "search": f'drug_name:"{drug_name}"',
            "limit": 20,
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            logger.warning("Failed to get interactions for '%s': %s", drug_name, e)
            return []

    def get_drug_adverse_events(
        self, drug_name: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get adverse event reports for a drug."""
        url = f"{OPENFDA_BASE}/event.json"
        params = {
            "search": f'patient.drug.openfda.generic_name:"{drug_name}"',
            "limit": limit,
        }

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(
                    {
                        "event_id": item.get("safetyreport_id"),
                        "date": item.get("receivedate"),
                        "outcomes": item.get("patient", {}).get("outcome", []),
                    }
                )
            return results
        except Exception as e:
            logger.warning("Failed to get adverse events for '%s': %s", drug_name, e)
            return []

    def _fetch_drug_data(self) -> dict[str, Any]:
        """Fetch drug data."""
        # Just return structure, actual queries are on-demand
        return {
            "provider_id": "openfda",
            "version": "online",
            "entities": {},
            "papers": [],
            "relationships": {},
        }


def get_openfda_provider() -> OpenFDAProvider:
    """Get configured OpenFDA provider."""
    return OpenFDAProvider()
