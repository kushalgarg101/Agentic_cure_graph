"""PubMed E-utilities provider for Agentic Cure Graph.

Provides access to PubMed literature via NCBI E-utilities API.
https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from github_viz.providers import EvidenceProvider, ProviderMetadata

logger = logging.getLogger(__name__)

PUBMED_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
DEFAULT_MAX_RESULTS = 20
RATE_LIMIT_DELAY = 0.34  # ~3 requests per second max

# Keywords for entity extraction from MeSH terms
DISEASE_KEYWORDS = [
    "disease",
    "syndrome",
    "disorder",
    "condition",
    "parkinson",
    "diabetes",
    "cancer",
    "tumor",
    "alzheimer",
    "dementia",
    "arthritis",
    "cardiovascular",
    "hypertension",
    "heart",
    "renal",
    "kidney",
    "liver",
    "pulmonary",
    "respiratory",
    "infect",
    "viral",
    "bacterial",
    "inflammatory",
    "autoimmune",
    "neurological",
    "psychiatric",
    "depression",
    "anxiety",
    "schizophrenia",
    "epilepsy",
    "stroke",
    "chronic",
    "acute",
    "fibrosis",
    "neurodegenerative",
    "metabolic",
]

DRUG_KEYWORDS = [
    "drug",
    "pharmacologic",
    "therapeutic",
    "therapy",
    "treatment",
    "medication",
    "inhibitor",
    "agonist",
    "antagonist",
    "receptor",
    "blocker",
    "activator",
]

GENE_KEYWORDS = [
    "gene",
    "protein",
    "kinase",
    "receptor",
    "enzyme",
    "transporter",
    "channel",
    "factor",
    "expression",
    "mutation",
    "variant",
    "allele",
    "genome",
    "genetic",
]

PATHWAY_KEYWORDS = [
    "pathway",
    "signaling",
    "cascade",
    "metabolic",
    "biosynthesis",
    "pathogenesis",
]

# Known drugs for explicit matching
KNOWN_DRUGS = [
    "Metformin",
    "Aspirin",
    "Atorvastatin",
    "Rosiglitazone",
    "Sitagliptin",
    "Pioglitazone",
    "Levodopa",
    "Carbidopa",
    "Selegiline",
    "Ropinirole",
    "Pramipexole",
    "Amantadine",
    "Ibuprofen",
    "Naprosyn",
    "Acetaminophen",
    "Lisinopril",
    "Amlodipine",
    "Metoprolol",
    "Omeprazole",
    "Levothyroxine",
    "Insulin",
    "Glipizide",
    "Januvia",
    "Ozempic",
    "Trulicity",
    "Carbidopa",
    "Entacapone",
    "Tolcapone",
    "Rivastigmine",
    "Donepezil",
]

# Known diseases for explicit matching
KNOWN_DISEASES = [
    "Parkinson disease",
    "Parkinson's disease",
    "Alzheimer disease",
    "Alzheimer's disease",
    "Diabetes mellitus",
    "Type 2 diabetes",
    "Type 1 diabetes",
    "Hypertension",
    "Coronary artery disease",
    "Heart failure",
    "Atrial fibrillation",
    "Chronic obstructive pulmonary disease",
    "COPD",
    "Asthma",
    "Rheumatoid arthritis",
    "Osteoarthritis",
    "Lupus",
    "Multiple sclerosis",
    "Depression",
    "Anxiety",
    "Bipolar disorder",
    "Schizophrenia",
    "Epilepsy",
    "Stroke",
    "Migraine",
    "Chronic kidney disease",
    "Non-alcoholic fatty liver disease",
    "Cirrhosis",
    "Cancer",
    "Tumor",
]


@dataclass
class PubMedProvider(EvidenceProvider):
    """PubMed E-utilities evidence provider."""

    api_key: str | None = None
    max_results: int = DEFAULT_MAX_RESULTS

    def __init__(
        self, api_key: str | None = None, max_results: int = DEFAULT_MAX_RESULTS
    ):
        self.api_key = api_key or os.getenv("PUBMED_API_KEY")
        self.max_results = max_results

    def describe(self) -> ProviderMetadata:
        return ProviderMetadata(
            provider_id="pubmed",
            version="online",
            description="PubMed biomedical literature via NCBI E-utilities",
            kind="online_api",
            location="https://pubmed.ncbi.nlm.nih.gov/",
        )

    def load(self) -> dict[str, Any]:
        return self._fetch_all_papers()

    def search_papers(
        self,
        query: str,
        max_results: int | None = None,
    ) -> list[dict[str, Any]]:
        """Search for papers matching a query."""
        max_results = max_results or self.max_results

        # Step 1: Search for IDs
        search_url = f"{PUBMED_EUTILS_BASE}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        response = requests.get(search_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        id_list = data.get("esearchresult", {}).get("idlist", [])
        if not id_list:
            return []

        # Rate limiting
        time.sleep(RATE_LIMIT_DELAY)

        # Step 2: Fetch details
        fetch_url = f"{PUBMED_EUTILS_BASE}/efetch.fcgi"
        params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml",
            "rettype": "abstract",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        response = requests.get(fetch_url, params=params, timeout=30)
        response.raise_for_status()

        # Parse XML to extract paper info
        papers = self._parse_pubmed_xml(response.text, id_list)

        return papers

    def search_by_disease(
        self, disease: str, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Search papers related to a disease."""
        return self.search_papers(
            f"{disease}[Title/Abstract] OR {disease}[MeSH Terms]",
            max_results=max_results,
        )

    def search_by_drug(
        self, drug: str, max_results: int | None = None
    ) -> list[dict[str, Any]]:
        """Search papers related to a drug."""
        return self.search_papers(
            f"{drug}[Title/Abstract] OR {drug}[MeSH Terms]", max_results=max_results
        )

    def search_drug_disease(self, drug: str, disease: str) -> list[dict[str, Any]]:
        """Search papers about a drug-disease relationship."""
        query = f"({drug}[Title/Abstract]) AND ({disease}[Title/Abstract])"
        return self.search_papers(query)

    def _fetch_all_papers(self) -> dict[str, Any]:
        """Fetch papers for common disease-drug pairs."""
        papers = []

        # Search for some common queries
        queries = [
            "Parkinson's disease treatment",
            "diabetes drug therapy",
            "cancer immunotherapy",
            "Alzheimer's disease",
            "metformin inflammation",
        ]

        for query in queries:
            try:
                results = self.search_papers(query, max_results=5)
                papers.extend(results)
                time.sleep(RATE_LIMIT_DELAY)
            except Exception as e:
                logger.warning("Failed to search '%s': %s", query, e)

        return {
            "provider_id": "pubmed",
            "version": "online",
            "entities": {},
            "papers": papers,
            "relationships": {},
        }

    def _parse_pubmed_xml(
        self, xml_text: str, id_list: list[str]
    ) -> list[dict[str, Any]]:
        """Parse PubMed XML response into structured format."""
        papers = []

        import xml.etree.ElementTree as ET

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return papers

        for article in root.findall(".//PubmedArticle"):
            try:
                # Get PMID
                pmid_elem = article.find(".//PMID")
                pmid = pmid_elem.text if pmid_elem is not None else ""

                # Get title
                title_elem = article.find(".//ArticleTitle")
                title = title_elem.text if title_elem is not None else ""

                # Get abstract
                abstract_parts = []
                for abstract_text in article.findall(".//AbstractText"):
                    if abstract_text.text:
                        abstract_parts.append(abstract_text.text)
                abstract = " ".join(abstract_parts)

                # Get journal info
                journal_elem = article.find(".//Journal/Title")
                journal = journal_elem.text if journal_elem is not None else ""

                year_elem = article.find(".//PubDate/Year")
                year = year_elem.text if year_elem is not None else ""

                # Get authors
                authors = []
                for author in article.findall(".//Author")[:5]:
                    last_name = author.find("LastName")
                    fore_name = author.find("ForeName")
                    if last_name is not None:
                        name = f"{last_name.text}"
                        if fore_name is not None:
                            name += f" {fore_name.text}"
                        authors.append(name)

                # Get MeSH terms
                mesh_terms = self._extract_mesh_terms(article)

                # Extract entities from title, abstract, and MeSH terms
                entities = self._extract_entities(title, abstract, mesh_terms)

                papers.append(
                    {
                        "id": f"pubmed:{pmid}",
                        "title": title,
                        "abstract_snippet": abstract[:500] if abstract else "",
                        "journal": journal,
                        "year": int(year) if year and year.isdigit() else None,
                        "authors": authors,
                        "citation": f"{journal} ({year})" if journal and year else "",
                        "mesh_terms": mesh_terms,
                        "entities": entities,
                    }
                )
            except Exception as e:
                logger.debug("Failed to parse article: %s", e)
                continue

        return papers

    def _extract_mesh_terms(self, article) -> list[str]:
        """Extract MeSH terms from a PubMed article."""
        mesh_terms = []
        mesh_heading_list = article.find(".//MeshHeadingList")
        if mesh_heading_list is not None:
            for mesh in mesh_heading_list.findall("MeshHeading"):
                descriptor = mesh.find("DescriptorName")
                if descriptor is not None and descriptor.text:
                    mesh_terms.append(descriptor.text)
        return mesh_terms

    def _extract_entities(
        self, title: str, abstract: str, mesh_terms: list[str]
    ) -> list[str]:
        """Extract biomedical entities from title, abstract, and MeSH terms."""
        entities = set()

        # Add relevant MeSH terms as entities
        for term in mesh_terms:
            term_lower = term.lower()
            # Filter for clinically relevant terms
            if any(kw in term_lower for kw in DISEASE_KEYWORDS):
                entities.add(term)
            elif any(kw in term_lower for kw in DRUG_KEYWORDS):
                entities.add(term)
            elif any(kw in term_lower for kw in GENE_KEYWORDS):
                entities.add(term)
            elif any(kw in term_lower for kw in PATHWAY_KEYWORDS):
                entities.add(term)

        # Extract from title and abstract using keyword matching
        title_str = title or ""
        abstract_str = abstract or ""
        text = f"{title_str} {abstract_str}".lower()

        # Look for drug mentions
        for drug in KNOWN_DRUGS:
            if drug.lower() in text:
                entities.add(drug)

        # Look for disease mentions in text
        for disease in KNOWN_DISEASES:
            if disease.lower() in text:
                entities.add(disease)

        return list(entities)


def get_pubmed_provider() -> PubMedProvider:
    """Get configured PubMed provider."""
    return PubMedProvider(api_key=os.getenv("PUBMED_API_KEY"))
