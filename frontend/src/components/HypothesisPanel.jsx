import React, { useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  Bot,
  FlaskConical,
  Microscope,
  ShieldAlert,
} from 'lucide-react';
import './HypothesisPanel.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';

export default function HypothesisPanel({
  hypotheses,
  evidenceItems,
  patientSummary,
  warnings,
  isProcessing,
}) {
  const [enrichingId, setEnrichingId] = useState(null);
  const [enrichments, setEnrichments] = useState({});

  const evidenceByHypothesis = Object.fromEntries(
    (evidenceItems || []).map((item) => [item.hypothesis_id, item]),
  );

  const handleEnrich = async (hypothesis) => {
    if (!patientSummary) {
      return;
    }

    setEnrichingId(hypothesis.id);

    try {
      const response = await fetch(`${API_BASE}/enrich`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hypothesis_id: hypothesis.id,
          patient_summary: patientSummary,
          hypothesis_label: hypothesis.label,
          hypothesis_mechanism: hypothesis.summary || hypothesis.mechanism || '',
        }),
      });

      if (response.ok) {
        const payload = await response.json();
        setEnrichments((current) => ({
          ...current,
          [hypothesis.id]: payload.enrichment,
        }));
      }
    } catch (error) {
      console.error('Enrichment failed', error);
    } finally {
      setEnrichingId(null);
    }
  };

  return (
    <div className="hypothesis-panel glass-panel">
      <div className="panel-header">
        <Microscope className="icon-green" size={24} />
        <h2>Ranked Hypotheses</h2>
        <span className="badge">{hypotheses.length} Found</span>
      </div>

      {patientSummary && (
        <div className="patient-summary-card">
          <span className="panel-section-label">Patient Summary</span>
          <p>{patientSummary}</p>
        </div>
      )}

      {warnings?.length > 0 && (
        <div className="warnings-card">
          <div className="warnings-header">
            <ShieldAlert size={16} />
            <span>Analysis Limitations</span>
          </div>
          <ul className="warnings-list">
            {warnings.map((warning) => (
              <li key={warning}>
                <AlertTriangle size={12} />
                <span>{warning}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {isProcessing && hypotheses.length === 0 && (
        <div className="empty-state">
          <p>Waiting for analysis results...</p>
        </div>
      )}

      {!isProcessing && (!hypotheses || hypotheses.length === 0) && (
        <div className="empty-state">
          <p>No hypotheses generated yet.</p>
        </div>
      )}

      <div className="hypothesis-list">
        {hypotheses.map((hypothesis, index) => {
          const evidence = evidenceByHypothesis[hypothesis.id];
          const papers = evidence?.papers || [];
          const providers = hypothesis.provenance?.providers || evidence?.provenance?.providers || [];
          const summary = hypothesis.summary || hypothesis.mechanism || '';

          return (
            <div key={hypothesis.id || index} className="hypothesis-card glass-panel">
              <div className="hyp-header">
                <span className="hyp-score">
                  Score: {typeof hypothesis.score === 'number' ? hypothesis.score.toFixed(2) : '—'}
                </span>
                <span className="hyp-rank">#{index + 1}</span>
              </div>

              <div className="hyp-title-row">
                <p className="hyp-label">{hypothesis.label || 'Unknown hypothesis'}</p>
                {hypothesis.classification && (
                  <span className={`hyp-classification hyp-classification-${hypothesis.classification}`}>
                    {hypothesis.classification.replaceAll('_', ' ')}
                  </span>
                )}
              </div>

              {summary && <p className="hyp-narrative">{summary}</p>}

              {hypothesis.meta?.rationale && (
                <p className="hyp-rationale">{hypothesis.meta.rationale}</p>
              )}

              <div className="hyp-metrics">
                <div className="hyp-metric">
                  <BookOpen size={14} />
                  <span>{hypothesis.evidence_count ?? papers.length} papers</span>
                </div>
                {hypothesis.meta?.biomarker_overlap?.length > 0 && (
                  <div className="hyp-metric">
                    <FlaskConical size={14} />
                    <span>{hypothesis.meta.biomarker_overlap.join(', ')}</span>
                  </div>
                )}
              </div>

              {providers.length > 0 && (
                <div className="hyp-provider-row">
                  {providers.map((provider) => (
                    <span key={provider} className="hyp-provider-pill">{provider}</span>
                  ))}
                </div>
              )}

              {papers.length > 0 && (
                <div className="hyp-evidence-block">
                  <span className="panel-section-label">Supporting Papers</span>
                  <ul className="paper-list">
                    {papers.slice(0, 3).map((paper) => (
                      <li key={paper.id}>
                        <span className="paper-title">{paper.title}</span>
                        <span className="paper-meta">
                          {[paper.journal, paper.year].filter(Boolean).join(' · ') || paper.provider_id}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="hyp-ai-section">
                {enrichments[hypothesis.id] ? (
                  <div className="ai-insight-box">
                    <Bot size={14} className="icon-cyan" />
                    <p>{enrichments[hypothesis.id]}</p>
                  </div>
                ) : (
                  <button
                    className="btn-text ai-action-btn"
                    onClick={() => handleEnrich(hypothesis)}
                    disabled={enrichingId === hypothesis.id}
                  >
                    {enrichingId === hypothesis.id ? (
                      <>
                        <Activity size={12} className="spinner" />
                        <span>Analyzing...</span>
                      </>
                    ) : (
                      <>
                        <Bot size={12} />
                        <span>View AI Reasoning</span>
                      </>
                    )}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
