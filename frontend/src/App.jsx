import React, { useState, useEffect } from 'react';
import InputPanel from './components/InputPanel';
import GraphCanvas from './components/GraphCanvas';
import HypothesisPanel from './components/HypothesisPanel';
import './App.css';

const API_BASE = "http://localhost:8000";

function App() {
  const [sessionId, setSessionId] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [graphData, setGraphData] = useState({ nodes: [], links: [] });
  const [hypotheses, setHypotheses] = useState([]);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  // ── helpers ──────────────────────────────────────────────────────────

  /**
   * Parse the free-text patient narrative into the structured
   * PatientCase schema the backend expects, plus forward the raw
   * text as report_text.
   */
  const buildRequestBody = (text) => {
    const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
    const extract = (prefix) =>
      lines
        .filter(l => l.toLowerCase().startsWith(prefix))
        .map(l => l.replace(/^[^:]+:\s*/i, '').trim())
        .filter(Boolean);

    return {
      patient_case: {
        patient_id: "demo-patient",
        age_range: extract("age:")[0] || "60-69",
        sex: "unknown",
        diagnoses: extract("diagnosis:").concat(extract("diagnoses:")),
        symptoms: extract("symptoms:").flatMap(s => s.split(',').map(t => t.trim())),
        biomarkers: extract("biomarker:").concat(extract("biomarkers:")),
        medications: extract("medication:").concat(extract("medications:")),
      },
      report_text: text,
      evidence_mode: "offline",
      with_ai: false,
      ai: null,
    };
  };

  // ── data fetching ───────────────────────────────────────────────────

  const fetchGraphData = async (sid) => {
    try {
      const [graphRes, statsRes, hypRes] = await Promise.all([
        fetch(`${API_BASE}/graph/${sid}`),
        fetch(`${API_BASE}/graph/${sid}/stats`),
        fetch(`${API_BASE}/graph/${sid}/hypotheses`),
      ]);

      if (graphRes.ok) {
        const gd = await graphRes.json();
        // ForceGraph2D expects { nodes: [...], links: [...] }
        setGraphData({
          nodes: gd.nodes || [],
          links: gd.links || [],
        });
      }

      if (statsRes.ok) {
        setStats(await statsRes.json());
      }

      if (hypRes.ok) {
        const hypData = await hypRes.json();
        // Backend returns { items: [...] }
        setHypotheses(hypData.items || []);
      }
    } catch (err) {
      console.error("Error fetching graph data:", err);
      setError("Failed to load graph data. Please try again.");
    }
  };

  // ── submit handler ──────────────────────────────────────────────────

  const handlePatientSubmit = async (text) => {
    setIsProcessing(true);
    setError(null);
    setGraphData({ nodes: [], links: [] });
    setHypotheses([]);
    setStats(null);

    try {
      const body = buildRequestBody(text);
      const response = await fetch(`${API_BASE}/analyze/local`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `Server responded with ${response.status}`);
      }

      const data = await response.json();

      // Backend returns { id, status, graph }
      const sid = data.id;
      if (!sid) {
        throw new Error("No session ID returned from backend.");
      }
      setSessionId(sid);

      // /analyze/local is synchronous – if status is "done" the graph is
      // already in the response, but we fetch via dedicated endpoints to
      // keep the data flow uniform and to get computed stats.
      if (data.status === "done") {
        setIsProcessing(false);
        fetchGraphData(sid);
      }
      // Otherwise the polling effect below will pick it up.
    } catch (err) {
      console.error("Error submitting patient data:", err);
      setError(err.message || "Submission failed.");
      setIsProcessing(false);
    }
  };

  // ── polling (for the async /analyze endpoint, kept as safety net) ──

  useEffect(() => {
    let intervalId;
    if (sessionId && isProcessing) {
      intervalId = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_BASE}/analyze/status/${sessionId}`);
          if (statusRes.ok) {
            const statusData = await statusRes.json();
            // Backend uses "done" / "error" (not "completed" / "failed")
            if (statusData.status === "done") {
              setIsProcessing(false);
              clearInterval(intervalId);
              fetchGraphData(sessionId);
            } else if (statusData.status === "error") {
              setIsProcessing(false);
              clearInterval(intervalId);
              setError(statusData.detail || "Analysis failed on the server.");
            }
          }
        } catch (err) {
          console.error("Polling error:", err);
        }
      }, 2000);
    }
    return () => clearInterval(intervalId);
  }, [sessionId, isProcessing]);

  // ── render ──────────────────────────────────────────────────────────

  return (
    <div className="app-container">
      <div className="sidebar-left">
        <InputPanel onSubmit={handlePatientSubmit} isProcessing={isProcessing} />
        {error && (
          <div className="error-banner">
            <p>{error}</p>
          </div>
        )}
      </div>

      <div className="main-canvas">
        <div className="canvas-header">
          {isProcessing && (
            <div className="status-indicator">
              <span className="status-dot pulsing"></span>
              <span className="status-text">Agentic Processing Active...</span>
            </div>
          )}
        </div>
        <GraphCanvas graphData={graphData} />

        {stats && !isProcessing && (
          <div className="stats-overlay glass-panel">
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
        <HypothesisPanel hypotheses={hypotheses} />
      </div>
    </div>
  );
}

export default App;
