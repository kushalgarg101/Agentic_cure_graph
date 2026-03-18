import React, { useState } from 'react';
import { Microscope, ArrowRight, BookOpen, FlaskConical, Bot, Activity } from 'lucide-react';
import './HypothesisPanel.css';

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export default function HypothesisPanel({ hypotheses, patientSummary }) {
    const [enrichingId, setEnrichingId] = useState(null);
    const [enrichments, setEnrichments] = useState({});

    const handleEnrich = async (hyp) => {
        if (!patientSummary) return;
        setEnrichingId(hyp.id);

        try {
            const response = await fetch(`${API_BASE}/enrich`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    hypothesis_id: hyp.id,
                    patient_summary: patientSummary,
                    hypothesis_label: hyp.label,
                    hypothesis_mechanism: hyp.summary || ""
                })
            });

            if (response.ok) {
                const data = await response.json();
                setEnrichments(prev => ({
                    ...prev,
                    [hyp.id]: data.enrichment
                }));
            }
        } catch (err) {
            console.error("Enrichment failed", err);
        } finally {
            setEnrichingId(null);
        }
    };

    if (!hypotheses || hypotheses.length === 0) {
        return (
            <div className="hypothesis-panel glass-panel">
                <div className="panel-header">
                    <Microscope className="icon-green" size={24} />
                    <h2>Discovery Engine</h2>
                </div>
                <div className="empty-state">
                    <p>No hypotheses generated yet.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="hypothesis-panel glass-panel">
            <div className="panel-header">
                <Microscope className="icon-green" size={24} />
                <h2>Ranked Hypotheses</h2>
                <span className="badge">{hypotheses.length} Found</span>
            </div>

            <div className="hypothesis-list">
                {hypotheses.map((hyp, index) => (
                    <div key={hyp.id || index} className="hypothesis-card glass-panel">
                        <div className="hyp-header">
                            <span className="hyp-score">
                                Score: {typeof hyp.score === 'number' ? hyp.score.toFixed(2) : '—'}
                            </span>
                            <span className="hyp-rank">#{index + 1}</span>
                        </div>

                        {/* label = "Drug for Disease" */}
                        <p className="hyp-label">{hyp.label || "Unknown hypothesis"}</p>

                        {/* summary = mechanism of action */}
                        {hyp.summary && (
                            <p className="hyp-narrative">{hyp.summary}</p>
                        )}

                        {/* rationale from meta */}
                        {hyp.meta?.rationale && (
                            <p className="hyp-rationale">{hyp.meta.rationale}</p>
                        )}

                        {/* drug → disease path chip */}
                        {hyp.meta?.drug && hyp.meta?.disease && (
                            <div className="hyp-path">
                                <span className="path-node">{hyp.meta.drug}</span>
                                <ArrowRight size={14} className="path-arrow" />
                                <span className="path-node">{hyp.meta.disease}</span>
                            </div>
                        )}

                        {/* evidence count */}
                        <div className="hyp-papers">
                            <BookOpen size={14} />
                            <span>
                                {hyp.evidence_count ?? hyp.meta?.supporting_paper_ids?.length ?? 0} Supporting Papers
                            </span>
                        </div>

                        {/* biomarker overlap */}
                        {hyp.meta?.biomarker_overlap?.length > 0 && (
                            <div className="hyp-biomarkers">
                                <FlaskConical size={14} />
                                <span>Biomarker: {hyp.meta.biomarker_overlap.join(', ')}</span>
                            </div>
                        )}

                        {/* AI Enrichment Section */}
                        <div className="hyp-ai-section">
                            {enrichments[hyp.id] ? (
                                <div className="ai-insight-box">
                                    <Bot size={14} className="icon-cyan" />
                                    <p>{enrichments[hyp.id]}</p>
                                </div>
                            ) : (
                                <button
                                    className="btn-text ai-action-btn"
                                    onClick={() => handleEnrich(hyp)}
                                    disabled={enrichingId === hyp.id}
                                >
                                    {enrichingId === hyp.id ? (
                                        <><Activity size={12} className="spinner" /> Analyzing...</>
                                    ) : (
                                        <><Bot size={12} /> View AI Reasoning</>
                                    )}
                                </button>
                            )}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
