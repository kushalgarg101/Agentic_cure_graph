"""Real-time evidence fetcher for Agentic Cure Graph.

Fetches live biomedical data from PubMed, ChEMBL, and OpenFDA APIs
based on patient diagnoses and medications.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any

import requests

logger = logging.getLogger(__name__)

MAX_WORKERS = 4
RATE_LIMIT_DELAY = 0.34  # ~3 requests per second


@dataclass
class EvidenceBundle:
    """Container for fetched evidence data in seed-like format."""

    entities: dict[str, list[dict]]
    papers: list[dict]
    relationships: dict[str, list[dict]]
    providers_used: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": self.entities,
            "papers": self.papers,
            "relationships": self.relationships,
            "providers_used": self.providers_used,
        }


class EvidenceFetcher:
    """Fetches real-time evidence from biomedical APIs."""

    def __init__(self):
        self._pubmed = None
        self._chembl = None
        self._openfda = None
        self._initialized = False

    def _ensure_initialized(self):
        """Lazy initialization of API clients."""
        if self._initialized:
            return

        # Import here to avoid circular imports
        try:
            from github_viz.data_providers.pubmed_api import get_pubmed_provider

            self._pubmed = get_pubmed_provider()
        except Exception as e:
            logger.warning("PubMed provider unavailable: %s", e)

        try:
            from github_viz.data_providers.chembl_api import get_chembl_provider

            self._chembl = get_chembl_provider()
        except Exception as e:
            logger.warning("ChEMBL provider unavailable: %s", e)

        try:
            from github_viz.data_providers.openfda_api import get_openfda_provider

            self._openfda = get_openfda_provider()
        except Exception as e:
            logger.warning("OpenFDA provider unavailable: %s", e)

        self._initialized = True

    def fetch_for_patient(self, patient_case: dict[str, Any]) -> EvidenceBundle:
        """Fetch all evidence for a patient's conditions."""
        self._ensure_initialized()

        diagnoses = patient_case.get("diagnoses", [])
        medications = patient_case.get("medications", [])

        all_papers = []
        all_drug_targets = []
        all_drug_info = []
        providers = []

        # Fetch papers from PubMed for each diagnosis
        if self._pubmed and diagnoses:
            papers = self._fetch_pubmed_papers(diagnoses)
            all_papers.extend(papers)
            providers.append("pubmed")

        # Fetch drug targets from ChEMBL
        if self._chembl and medications:
            targets = self._fetch_chembl_targets(medications)
            all_drug_targets.extend(targets)
            providers.append("chembl")

        # Fetch drug info from OpenFDA
        if self._openfda and medications:
            info = self._fetch_openfda_drugs(medications)
            all_drug_info.extend(info)
            providers.append("openfda")

        # Build evidence bundle in seed-like format
        return self._build_evidence_bundle(
            papers=all_papers,
            drug_targets=all_drug_targets,
            drug_info=all_drug_info,
            providers=providers,
            patient_medications=medications,
        )

    def _fetch_pubmed_papers(self, diagnoses: list[str]) -> list[dict[str, Any]]:
        """Fetch papers from PubMed for each diagnosis."""
        papers = []

        for disease in diagnoses:
            if not disease:
                continue
            try:
                results = self._pubmed.search_by_disease(disease, max_results=10)
                papers.extend(results)
                logger.info("PubMed: fetched %d papers for '%s'", len(results), disease)
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                logger.warning("PubMed search failed for '%s': %s", disease, e)

        return papers

    def _fetch_chembl_targets(self, medications: list[str]) -> list[dict[str, Any]]:
        """Fetch drug-target relationships from ChEMBL."""
        targets = []

        for drug in medications:
            if not drug:
                continue
            try:
                results = self._chembl.get_drug_targets(drug)
                targets.extend(results)
                logger.info("ChEMBL: fetched %d targets for '%s'", len(results), drug)
                time.sleep(0.5)  # ChEMBL rate limit
            except Exception as e:
                logger.warning("ChEMBL fetch failed for '%s': %s", drug, e)

        return targets

    def _fetch_openfda_drugs(self, medications: list[str]) -> list[dict[str, Any]]:
        """Fetch drug info from OpenFDA."""
        drugs = []

        for drug in medications:
            if not drug:
                continue
            try:
                results = self._openfda.search_drug(drug, limit=5)
                drugs.extend(results)
                logger.info("OpenFDA: fetched %d records for '%s'", len(results), drug)
                time.sleep(0.3)
            except Exception as e:
                logger.warning("OpenFDA fetch failed for '%s': %s", drug, e)

        return drugs

    def _build_evidence_bundle(
        self,
        papers: list[dict[str, Any]],
        drug_targets: list[dict[str, Any]],
        drug_info: list[dict[str, Any]],
        providers: list[str],
        patient_medications: list[str] | None = None,
    ) -> EvidenceBundle:
        """Convert API responses to seed-like format."""

        patient_medications = patient_medications or []

        # Build entities from papers
        entities: dict[str, list[dict]] = {
            "diseases": [],
            "drugs": [],
            "genes": [],
            "proteins": [],
            "pathways": [],
        }

        # Add patient medications to entities FIRST
        for med in patient_medications:
            if med:
                entities["drugs"].append({"id": f"drug:{med.lower()}", "label": med})

        # Extract entities from papers
        disease_set = set()
        drug_set = set()

        for paper in papers:
            entities_list = paper.get("entities", [])
            for entity in entities_list:
                entity_lower = entity.lower()
                if (
                    "disease" in entity_lower
                    or "parkinson" in entity_lower
                    or "diabetes" in entity_lower
                    or "cancer" in entity_lower
                    or "alzheimer" in entity_lower
                ):
                    if entity not in disease_set:
                        disease_set.add(entity)
                        entities["diseases"].append(
                            {"id": f"disease:{entity}", "label": entity}
                        )
                elif (
                    "drug" in entity_lower
                    or "metformin" in entity_lower
                    or "aspirin" in entity_lower
                ):
                    if entity not in drug_set:
                        drug_set.add(entity)
                        entities["drugs"].append(
                            {"id": f"drug:{entity}", "label": entity}
                        )

        # Add patient medications to entities
        for drug in drug_targets:
            drug_name = drug.get("chembl_id")
            if drug_name and drug_name not in drug_set:
                drug_set.add(drug_name)
                entities["drugs"].append(
                    {"id": f"drug:{drug_name}", "label": drug_name}
                )

        # Build relationships
        relationships: dict[str, list[dict]] = {
            "drug_target": [],
            "gene_disease": [],
            "drug_hypotheses": [],
        }

        # Convert drug targets
        for target in drug_targets:
            relationships["drug_target"].append(
                {
                    "drug": target.get("chembl_id", ""),
                    "protein": target.get("target_name", ""),
                    "effect": target.get("action_type", ""),
                    "papers": [],
                }
            )

        # Build hypotheses from papers and targets
        if papers and entities.get("diseases"):
            disease = entities["diseases"][0]["label"]

            # Find drugs mentioned in papers
            paper_drugs = set()
            for paper in papers:
                for entity in paper.get("entities", []):
                    if entity.lower() not in [
                        "parkinson's disease",
                        "diabetes",
                        "cancer",
                        "alzheimer's disease",
                    ]:
                        paper_drugs.add(entity)

            for drug in paper_drugs:
                hypothesis = {
                    "drug": drug,
                    "disease": disease,
                    "mechanism": papers[0].get("abstract_snippet", "")[:200]
                    if papers
                    else "",
                    "biomarker_matches": [],
                    "genes": [],
                    "proteins": [],
                    "pathways": [],
                    "papers": [p.get("id", "") for p in papers[:3]],
                }
                relationships["drug_hypotheses"].append(hypothesis)

        return EvidenceBundle(
            entities=entities,
            papers=papers,
            relationships=relationships,
            providers_used=providers,
        )


def get_evidence_fetcher() -> EvidenceFetcher:
    """Get singleton EvidenceFetcher instance."""
    return EvidenceFetcher()
