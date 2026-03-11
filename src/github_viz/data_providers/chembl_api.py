"""ChEMBL provider for Agentic Cure Graph.

Provides access to ChEMBL database via EBI API.
https://www.ebi.ac.uk/chembl/api/data
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import requests

from github_viz.providers import EvidenceProvider, ProviderMetadata

logger = logging.getLogger(__name__)

CHEMBL_API_BASE = "https://www.ebi.ac.uk/chembl/api/data"
RATE_LIMIT_DELAY = 0.5  # Be respectful to EBI servers


@dataclass
class ChEMBLProvider(EvidenceProvider):
    """ChEMBL evidence provider for drug-target interactions."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def describe(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id="chembl",
            version="online",
            description="ChEMBL database - drug-target interactions from EBI",
            kind="online_api",
            location="https://www.ebi.ac.uk/chembl/",
        )

    def load(self) -> dict[str, Any]:
        return self._fetch_drug_data()

    def search_drug(self, drug_name: str) -> list[dict[str, Any]]:
        """Search for a drug by name."""
        url = f"{CHEMBL_API_BASE}/molecule/search.json"
        params = {"q": drug_name, "limit": 10}

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            molecules = data.get("molecules", [])
            results = []
            for mol in molecules:
                results.append(
                    {
                        "chembl_id": mol.get("molecule_chembl_id"),
                        "name": mol.get("pref_name"),
                        "synonyms": mol.get("synonyms", []),
                        "drug_type": mol.get("molecule_type"),
                        "max_phase": mol.get("max_phase"),
                    }
                )
            return results
        except Exception as e:
            logger.warning("Failed to search drug '%s': %s", drug_name, e)
            return []

    def get_drug_targets(self, drug_name: str) -> list[dict[str, Any]]:
        """Get target information for a drug."""
        # First search for the drug
        drugs = self.search_drug(drug_name)
        if not drugs:
            return []

        chembl_id = drugs[0].get("chembl_id")
        if not chembl_id:
            return []

        # Get mechanisms
        url = f"{CHEMBL_API_BASE}/mechanism.json"
        params = {"molecule_chembl_id": chembl_id}

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            mechanisms = data.get("mechanisms", [])
            targets = []
            for mech in mechanisms:
                targets.append(
                    {
                        "chembl_id": chembl_id,
                        "target_name": mech.get("target_name"),
                        "target_chembl_id": mech.get("target_chembl_id"),
                        "mechanism": mech.get("mechanism"),
                        "action_type": mech.get("action_type"),
                    }
                )
            return targets
        except Exception as e:
            logger.warning("Failed to get targets for '%s': %s", drug_name, e)
            return []

    def search_disease_targets(self, disease: str) -> list[dict[str, Any]]:
        """Find targets related to a disease."""
        # Search for disease in indication data
        url = f"{CHEMBL_API_BASE}/indication.json"
        params = {"disease": disease, "limit": 20}

        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            indications = data.get("indications", [])
            results = []
            for ind in indications:
                results.append(
                    {
                        "disease": ind.get("disease"),
                        "disease_id": ind.get("disease_chembl_id"),
                        "drug_name": ind.get("drug_name"),
                        "chembl_id": ind.get("molecule_chembl_id"),
                        "phase": ind.get("max_phase"),
                    }
                )
            return results
        except Exception as e:
            logger.warning("Failed to search disease '%s': %s", disease, e)
            return []

    def _fetch_drug_data(self) -> dict[str, Any]:
        """Fetch common drug-target relationships."""
        drugs = [
            "metformin",
            "aspirin",
            "atorvastatin",
            "metformin",
            "rosiglitazone",
            "sitagliptin",
        ]

        all_targets = []

        for drug in drugs:
            try:
                targets = self.get_drug_targets(drug)
                all_targets.extend(targets)
            except Exception as e:
                logger.debug("Failed to get targets for %s: %s", drug, e)

        return {
            "provider_id": "chembl",
            "version": "online",
            "entities": {},
            "papers": [],
            "relationships": {"drug_target": all_targets},
        }


def get_chembl_provider() -> ChEMBLProvider:
    """Get configured ChEMBL provider."""
    return ChEMBLProvider()
