import React, { useEffect, useState } from 'react';
import InputPanel from './components/InputPanel';
import GraphCanvas from './components/GraphCanvas';
import HypothesisPanel from './components/HypothesisPanel';
import './App.css';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
const EMPTY_GRAPH = { nodes: [], links: [] };

function formatErrorDetail(detail, fallback) {
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        const location = Array.isArray(item?.loc) ? item.loc.join('.') : 'request';
        return `${location}: ${item?.msg || 'invalid value'}`;
      })
      .join('; ');
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail;
  }
  return fallback;
}

async function readJson(response, fallbackMessage) {
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(formatErrorDetail(payload?.detail, fallbackMessage));
  }
  return payload;
}

function App() {
  const [analysisId, setAnalysisId] = useState(null);
  const [analysisStatus, setAnalysisStatus] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [graphData, setGraphData] = useState(EMPTY_GRAPH);
  const [hypotheses, setHypotheses] = useState([]);
  const [evidenceItems, setEvidenceItems] = useState([]);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [dataSources, setDataSources] = useState([]);
  const [analysisProviders, setAnalysisProviders] = useState([]);

  const resetResults = () => {
    setGraphData(EMPTY_GRAPH);
    setHypotheses([]);
    setEvidenceItems([]);
    setStats(null);
    setWarnings([]);
    setAnalysisProviders([]);
  };

  useEffect(() => {
    let cancelled = false;

    const fetchDataSources = async () => {
      try {
        const response = await fetch(`${API_BASE}/datasets`);
        const payload = await readJson(response, 'Failed to load datasets.');
        if (!cancelled) {
          setDataSources((payload.items || []).map((item) => item.provider_id));
        }
      } catch (fetchError) {
        if (!cancelled) {
          console.error('Error fetching data sources:', fetchError);
        }
      }
    };

    fetchDataSources();

    return () => {
      cancelled = true;
    };
  }, []);

  const fetchAnalysisArtifacts = async (id, statusPayload) => {
    const [graphPayload, statsPayload, hypothesesPayload, evidencePayload] = await Promise.all([
      readJson(await fetch(`${API_BASE}/analyses/${id}/graph`), 'Failed to load graph.'),
      readJson(await fetch(`${API_BASE}/analyses/${id}/stats`), 'Failed to load stats.'),
      readJson(await fetch(`${API_BASE}/analyses/${id}/hypotheses`), 'Failed to load hypotheses.'),
      readJson(await fetch(`${API_BASE}/analyses/${id}/evidence`), 'Failed to load evidence.'),
    ]);

    setGraphData({
      nodes: graphPayload.nodes || [],
      links: graphPayload.links || [],
    });
    setStats(statsPayload);
    setHypotheses(hypothesesPayload.items || []);
    setEvidenceItems(evidencePayload.items || []);
    setWarnings([
      ...new Set([...(statusPayload?.warnings || []), ...(graphPayload.meta?.warnings || [])]),
    ]);
    setAnalysisProviders(
      (graphPayload.meta?.dataset_versions || []).map((item) => item.provider_id).filter(Boolean),
    );
  };

  const handlePatientSubmit = async (submission) => {
    setError(null);
    resetResults();
    setAnalysisId(null);
    setAnalysisStatus(null);
    setIsProcessing(true);

    try {
      let analysisRequest = submission.payload;

      if (submission.mode === 'fhir') {
        const parsed = JSON.parse(submission.fhirText);
        const record = parsed?.record && typeof parsed.record === 'object' ? parsed.record : parsed;
        const normalized = await readJson(
          await fetch(`${API_BASE}/fhir/normalize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ record }),
          }),
          'FHIR normalization failed.',
        );

        analysisRequest = {
          ...normalized,
          evidence_mode: submission.evidenceMode,
          input_format: 'fhir',
        };
      }

      const created = await readJson(
        await fetch(`${API_BASE}/analyses`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(analysisRequest),
        }),
        'Failed to start analysis.',
      );

      setAnalysisId(created.id);
      setAnalysisStatus(created.status);
    } catch (submitError) {
      console.error('Error submitting patient data:', submitError);
      setError(submitError.message || 'Submission failed.');
      setIsProcessing(false);
    }
  };

  useEffect(() => {
    if (!analysisId || !isProcessing) {
      return undefined;
    }

    let cancelled = false;

    const pollStatus = async () => {
      try {
        const payload = await readJson(
          await fetch(`${API_BASE}/analyses/${analysisId}`),
          'Failed to check analysis status.',
        );

        if (cancelled) {
          return;
        }

        setAnalysisStatus(payload.status);
        setWarnings(payload.warnings || []);

        if (payload.status === 'completed') {
          setIsProcessing(false);
          await fetchAnalysisArtifacts(analysisId, payload);
        } else if (payload.status === 'failed') {
          setIsProcessing(false);
          setError(payload.detail || 'Analysis failed on the server.');
        }
      } catch (statusError) {
        if (cancelled) {
          return;
        }
        console.error('Polling error:', statusError);
        setIsProcessing(false);
        setError(statusError.message || 'Status check failed.');
      }
    };

    pollStatus();
    const intervalId = setInterval(pollStatus, 2000);

    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [analysisId, isProcessing]);

  const visibleProviders = analysisProviders.length > 0 ? analysisProviders : dataSources;
  const patientSummary = stats?.patient_profile?.summary || stats?.patient_profile?.label || 'Patient case';

  return (
    <div className="app-container dashboard-mode">
      <div className="sidebar-left">
        <InputPanel onSubmit={handlePatientSubmit} isProcessing={isProcessing} />
      </div>

      <div className="main-canvas">
        <div className="canvas-header">
          {isProcessing && (
            <div className="status-indicator">
              <span className="status-dot pulsing"></span>
              <span className="status-text">
                {analysisStatus === 'running' ? 'Generating Cure Graph...' : 'Queued for analysis...'}
              </span>
            </div>
          )}
        </div>
        <GraphCanvas graphData={graphData} />

        {stats && !isProcessing && (
          <div className="stats-overlay glass-panel">
            <div className="data-sources">
              <span className="sources-label">Data Sources:</span>
              {visibleProviders.length > 0 ? (
                visibleProviders.map((source) => (
                  <span key={source} className="source-badge">{source}</span>
                ))
              ) : (
                <span className="source-badge">none</span>
              )}
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.total_nodes}</span>
              <span className="stat-label">Nodes</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.total_links}</span>
              <span className="stat-label">Edges</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.evidence_coverage?.hypothesis_nodes ?? 0}</span>
              <span className="stat-label">Hypotheses</span>
            </div>
            <div className="stat-item">
              <span className="stat-value">{stats.evidence_coverage?.paper_nodes ?? 0}</span>
              <span className="stat-label">Papers</span>
            </div>
          </div>
        )}
      </div>

      <div className="sidebar-right">
        <HypothesisPanel
          hypotheses={hypotheses}
          evidenceItems={evidenceItems}
          patientSummary={patientSummary}
          warnings={warnings}
          isProcessing={isProcessing}
        />
      </div>
    </div>
  );
}

export default App;
