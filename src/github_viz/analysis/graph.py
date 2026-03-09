"""Graph construction and enrichment pipeline for Agentic Cure Graph."""

from __future__ import annotations

import json
import logging
import pathlib
import time
import uuid

from github_viz.analysis.llm import enrich_case_summary
from github_viz.analysis.models import Link, Node
from github_viz.analysis.parser import build_extraction_dictionary, parse_patient_case

logger = logging.getLogger(__name__)

DATA_FILE = pathlib.Path(__file__).resolve().parent.parent / "data" / "seed_biomedical_graph.json"


def analyze_case(
    patient_case: dict,
    report_text: str,
    evidence_mode: str,
    with_ai: bool,
    ai_options: dict | None = None,
    evidence_bundle: dict | None = None,
) -> dict:
    """Analyze a patient case and return graph JSON consumed by API/UI."""
    started_at = time.monotonic()
    seed = evidence_bundle or load_seed_data()
    extraction_dictionary = build_extraction_dictionary(seed["entities"])
    parsed_case = parse_patient_case(patient_case, report_text, extraction_dictionary)

    nodes: dict[str, Node] = {}
    links: list[Link] = []
    label_index = build_label_index(seed)

    patient_node = Node(
        id=f"patient:{parsed_case.patient_id}",
        type="patient",
        label=f"Patient {parsed_case.patient_id}",
        summary=parsed_case.patient_summary(),
        group="patient",
        size=6,
        complexity=len(parsed_case.all_terms()) or 1,
        meta={
            "age_range": parsed_case.age_range,
            "sex": parsed_case.sex,
            "diagnoses": parsed_case.diagnoses,
            "symptoms": parsed_case.symptoms,
            "biomarkers": parsed_case.biomarkers,
            "medications": parsed_case.medications,
            "report_text": parsed_case.report_text,
            "narrative_entities": parsed_case.narrative_entities,
        },
    )
    nodes[patient_node.id] = patient_node

    matched_diseases = _attach_patient_terms(nodes, links, patient_node.id, parsed_case.diagnoses, "disease", "has_disease", label_index)
    matched_symptoms = _attach_patient_terms(nodes, links, patient_node.id, parsed_case.symptoms, "symptom", "has_symptom", label_index)
    matched_biomarkers = _attach_patient_terms(nodes, links, patient_node.id, parsed_case.biomarkers, "biomarker", "has_biomarker", label_index)
    matched_drugs = _attach_patient_terms(nodes, links, patient_node.id, parsed_case.medications, "drug", "takes_drug", label_index)

    matched_disease_labels = {entry.label for entry in matched_diseases.values()}
    matched_biomarker_labels = {entry.label for entry in matched_biomarkers.values()}

    _attach_evidence_network(nodes, links, seed, matched_disease_labels, matched_biomarker_labels)
    ranked_hypotheses = _build_hypotheses(
        nodes,
        links,
        seed,
        patient_node,
        matched_disease_labels,
        matched_biomarker_labels,
        {entry.label for entry in matched_drugs.values()},
    )

    patient_node.meta["observed_symptoms"] = [entry.label for entry in matched_symptoms.values()]

    ai_summary = {
        "enabled": with_ai,
        "status": "disabled",
        "patient_summary": patient_node.summary,
    }
    if with_ai:
        try:
            ai_summary = enrich_case_summary(
                patient_node.summary,
                [
                    {
                        "label": item.label,
                        "score": item.score,
                        "rationale": item.meta.get("rationale", ""),
                    }
                    for item in ranked_hypotheses
                ],
                ai_options=ai_options,
            )
            if ai_summary.get("patient_summary"):
                patient_node.summary = ai_summary["patient_summary"]
            if ranked_hypotheses and ai_summary.get("top_hypothesis_summary"):
                ranked_hypotheses[0].summary = ai_summary["top_hypothesis_summary"]
        except Exception as exc:
            logger.warning("AI enrichment failed: %s", exc)
            ai_summary = {
                "enabled": True,
                "status": "error",
                "detail": str(exc),
                "patient_summary": patient_node.summary,
            }

    _dedupe_links_in_place(links)
    elapsed = round(time.monotonic() - started_at, 2)
    return {
        "meta": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": str(uuid.uuid4()),
            "patient_case_summary": patient_node.summary,
            "evidence_mode": evidence_mode,
            "hypothesis_count": len(ranked_hypotheses),
            "analysis_time_s": elapsed,
            "seed_dataset_version": seed.get("version", "unknown"),
            "ai_summary": ai_summary,
        },
        "nodes": [node.to_dict() for node in nodes.values()],
        "links": [link.to_dict() for link in links],
    }


def load_seed_data() -> dict:
    with DATA_FILE.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def build_label_index(seed: dict) -> dict[str, dict]:
    index: dict[str, dict] = {}
    for type_name, items in seed.get("entities", {}).items():
        normalized_type = _singularize(type_name)
        for item in items:
            enriched = {**item, "type": normalized_type}
            index[str(item["label"]).casefold()] = enriched
            for alias in item.get("aliases", []):
                index[str(alias).casefold()] = enriched
    return index


def _attach_patient_terms(nodes, links, patient_id, items, node_type, relation_kind, label_index):
    attached: dict[str, Node] = {}
    for item in items:
        entity = label_index.get(str(item).casefold())
        if entity and entity.get("type") == node_type:
            node = _node_from_seed_entity(entity, node_type)
        else:
            node = Node(
                id=f"{node_type}:{_slug(item)}",
                type=node_type,
                label=item,
                summary=f"Patient-reported {node_type}.",
                group=node_type,
                size=3,
            )
        nodes.setdefault(node.id, node)
        attached[node.id] = nodes[node.id]
        links.append(Link(source=patient_id, target=node.id, kind=relation_kind, weight=2))
    return attached


def _attach_evidence_network(nodes, links, seed, matched_disease_labels, matched_biomarker_labels):
    papers_by_id = {paper["id"]: paper for paper in seed.get("papers", [])}
    label_index = build_label_index(seed)

    for relation in seed.get("relationships", {}).get("gene_disease", []):
        if relation["disease"] not in matched_disease_labels:
            continue
        gene = _node_from_seed_entity(label_index[relation["gene"].casefold()], "gene")
        disease = _node_from_seed_entity(label_index[relation["disease"].casefold()], "disease")
        nodes.setdefault(gene.id, gene)
        nodes.setdefault(disease.id, disease)
        links.append(Link(source=gene.id, target=disease.id, kind="associated_with", evidence_ids=relation.get("papers", [])))
        _attach_papers(nodes, links, papers_by_id, relation.get("papers", []), gene.id)

    for relation in seed.get("relationships", {}).get("protein_pathway", []):
        protein = _node_from_seed_entity(label_index[relation["protein"].casefold()], "protein")
        pathway = _node_from_seed_entity(label_index[relation["pathway"].casefold()], "pathway")
        nodes.setdefault(protein.id, protein)
        nodes.setdefault(pathway.id, pathway)
        links.append(Link(source=protein.id, target=pathway.id, kind="involves_pathway", evidence_ids=relation.get("papers", [])))
        _attach_papers(nodes, links, papers_by_id, relation.get("papers", []), pathway.id)

    for relation in seed.get("relationships", {}).get("pathway_disease", []):
        if relation["disease"] not in matched_disease_labels:
            continue
        pathway = _node_from_seed_entity(label_index[relation["pathway"].casefold()], "pathway")
        disease = _node_from_seed_entity(label_index[relation["disease"].casefold()], "disease")
        nodes.setdefault(pathway.id, pathway)
        nodes.setdefault(disease.id, disease)
        links.append(Link(source=pathway.id, target=disease.id, kind="associated_with", evidence_ids=relation.get("papers", [])))
        _attach_papers(nodes, links, papers_by_id, relation.get("papers", []), pathway.id)

    for relation in seed.get("relationships", {}).get("biomarker_pathway", []):
        if relation["biomarker"] not in matched_biomarker_labels:
            continue
        biomarker = _node_from_seed_entity(label_index[relation["biomarker"].casefold()], "biomarker")
        pathway = _node_from_seed_entity(label_index[relation["pathway"].casefold()], "pathway")
        nodes.setdefault(biomarker.id, biomarker)
        nodes.setdefault(pathway.id, pathway)
        links.append(Link(source=biomarker.id, target=pathway.id, kind="mentions", evidence_ids=relation.get("papers", [])))
        _attach_papers(nodes, links, papers_by_id, relation.get("papers", []), biomarker.id)

    for relation in seed.get("relationships", {}).get("drug_target", []):
        drug = _node_from_seed_entity(label_index[relation["drug"].casefold()], "drug")
        protein = _node_from_seed_entity(label_index[relation["protein"].casefold()], "protein")
        nodes.setdefault(drug.id, drug)
        nodes.setdefault(protein.id, protein)
        links.append(Link(source=drug.id, target=protein.id, kind="targets", evidence_ids=relation.get("papers", [])))
        _attach_papers(nodes, links, papers_by_id, relation.get("papers", []), drug.id)


def _build_hypotheses(nodes, links, seed, patient_node, matched_disease_labels, matched_biomarker_labels, matched_drug_labels):
    label_index = build_label_index(seed)
    papers_by_id = {paper["id"]: paper for paper in seed.get("papers", [])}
    ranked: list[Node] = []

    for relation in seed.get("relationships", {}).get("drug_hypotheses", []):
        if relation["disease"] not in matched_disease_labels:
            continue
        drug_entity = label_index[relation["drug"].casefold()]
        disease_entity = label_index[relation["disease"].casefold()]
        drug_node = _node_from_seed_entity(drug_entity, "drug")
        disease_node = _node_from_seed_entity(disease_entity, "disease")
        nodes.setdefault(drug_node.id, drug_node)
        nodes.setdefault(disease_node.id, disease_node)

        biomarker_overlap = sorted(set(relation.get("biomarker_matches", [])) & matched_biomarker_labels)
        paper_ids = relation.get("papers", [])
        score = _score_hypothesis(relation, biomarker_overlap, matched_drug_labels)
        hypothesis_id = f"hypothesis:{_slug(relation['drug'])}:{_slug(relation['disease'])}"
        rationale = (
            f"Matched disease {relation['disease']} with {len(paper_ids)} supporting papers "
            f"and {len(biomarker_overlap)} biomarker overlaps."
        )

        hypothesis_node = Node(
            id=hypothesis_id,
            type="hypothesis",
            label=f"{relation['drug']} for {relation['disease']}",
            summary=relation["mechanism"],
            group="hypothesis",
            size=5,
            complexity=len(relation.get("pathways", [])) + len(relation.get("genes", [])),
            score=score,
            evidence_count=len(paper_ids),
            meta={
                "drug": relation["drug"],
                "disease": relation["disease"],
                "rationale": rationale,
                "biomarker_overlap": biomarker_overlap,
                "supporting_paper_ids": paper_ids,
                "evidence_breakdown": {
                    "paper_count": len(paper_ids),
                    "gene_count": len(relation.get("genes", [])),
                    "pathway_count": len(relation.get("pathways", [])),
                },
            },
        )
        nodes[hypothesis_id] = hypothesis_node
        ranked.append(hypothesis_node)

        links.append(Link(source=patient_node.id, target=hypothesis_id, kind="candidate_treatment_for", weight=2, evidence_ids=paper_ids))
        links.append(Link(source=hypothesis_id, target=drug_node.id, kind="references_drug", evidence_ids=paper_ids))
        links.append(Link(source=hypothesis_id, target=disease_node.id, kind="candidate_treatment_for", evidence_ids=paper_ids))

        for pathway_name in relation.get("pathways", []):
            pathway_node = _node_from_seed_entity(label_index[pathway_name.casefold()], "pathway")
            nodes.setdefault(pathway_node.id, pathway_node)
            links.append(Link(source=hypothesis_id, target=pathway_node.id, kind="mentions", evidence_ids=paper_ids))

        for gene_name in relation.get("genes", []):
            gene_node = _node_from_seed_entity(label_index[gene_name.casefold()], "gene")
            nodes.setdefault(gene_node.id, gene_node)
            links.append(Link(source=hypothesis_id, target=gene_node.id, kind="mentions", evidence_ids=paper_ids))

        for paper_id in paper_ids:
            _attach_papers(nodes, links, papers_by_id, [paper_id], hypothesis_id)

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked


def _attach_papers(nodes, links, papers_by_id, paper_ids, source_id):
    for paper_id in paper_ids:
        paper = papers_by_id.get(paper_id)
        if not paper:
            continue
        node = Node(
            id=paper_id,
            type="research_paper",
            label=paper["title"],
            summary=paper.get("abstract_snippet", ""),
            group="evidence",
            size=2,
            evidence_count=1,
            meta={
                "journal": paper.get("journal", ""),
                "year": paper.get("year", ""),
                "citation": paper.get("citation", ""),
                "entities": paper.get("entities", []),
                "provider_id": paper.get("provider_id", "curated_seed"),
            },
        )
        nodes.setdefault(node.id, node)
        links.append(Link(source=source_id, target=node.id, kind="supported_by", evidence_ids=[paper_id]))


def _node_from_seed_entity(entity: dict, node_type: str) -> Node:
    return Node(
        id=entity["id"],
        type=node_type,
        label=entity["label"],
        summary=f"Seeded {node_type} in the curated biomedical evidence pack.",
        group=node_type,
        size=3,
        meta={"aliases": entity.get("aliases", [])},
    )


def _score_hypothesis(relation: dict, biomarker_overlap: list[str], matched_drug_labels: set[str]) -> float:
    score = 0.35
    score += min(0.24, len(relation.get("papers", [])) * 0.08)
    score += min(0.18, len(biomarker_overlap) * 0.09)
    score += min(0.12, len(relation.get("pathways", [])) * 0.04)
    if relation.get("drug") in matched_drug_labels:
        score += 0.08
    return round(min(0.99, score), 3)


def _dedupe_links_in_place(links: list[Link]) -> None:
    merged: dict[tuple[str, str, str], Link] = {}
    for link in links:
        key = (link.source, link.target, link.kind)
        if key in merged:
            merged[key].weight += link.weight
            merged[key].evidence_ids = sorted(set(merged[key].evidence_ids + link.evidence_ids))
        else:
            merged[key] = Link(
                source=link.source,
                target=link.target,
                kind=link.kind,
                weight=link.weight,
                evidence_ids=list(link.evidence_ids),
            )
    links[:] = list(merged.values())


def _singularize(name: str) -> str:
    if name.endswith("ies"):
        return f"{name[:-3]}y"
    return name[:-1] if name.endswith("s") else name


def _slug(value: str) -> str:
    cleaned = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    while "--" in cleaned:
        cleaned = cleaned.replace("--", "-")
    return cleaned.strip("-")
