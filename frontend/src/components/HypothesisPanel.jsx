import React from 'react';
import { Microscope, ArrowRight, BookOpen, FlaskConical } from 'lucide-react';
import './HypothesisPanel.css';

export default function HypothesisPanel({ hypotheses }) {
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
                                <span>Biomarker overlap: {hyp.meta.biomarker_overlap.join(', ')}</span>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </div>
    );
}
