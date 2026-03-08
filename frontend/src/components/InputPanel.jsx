import React, { useState } from 'react';
import { Bot, Activity, BrainCircuit, Sparkles, FileText } from 'lucide-react';
import './InputPanel.css';

const EXAMPLES = {
  parkinsons: "Diagnosis: Parkinson's disease\nBiomarker: elevated inflammation\nMedication: Metformin\nAge: 68\nSymptoms: Resting tremor, bradykinesia.",
  alzheimers: "Diagnosis: Alzheimer's disease\nBiomarker: amyloid plaques\nMedication: Donepezil\nAge: 72\nSymptoms: Memory loss, confusion."
};

export default function InputPanel({ onSubmit, isProcessing }) {
  const [patientData, setPatientData] = useState(EXAMPLES.parkinsons);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!patientData.trim()) return;
    onSubmit(patientData);
  };

  return (
    <div className="input-panel glass-panel">
      <div className="panel-header">
        <div className="icon-wrapper">
          <BrainCircuit className="icon-cyan" size={28} />
        </div>
        <div>
          <h2>Patient Intelligence</h2>
          <span className="subtitle-badge">Agentic Extraction</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="input-form">
        <div className="form-header">
          <label htmlFor="patient-data">Synthetic Patient Narrative</label>
        </div>

        <div className="textarea-wrapper">
          <textarea
            id="patient-data"
            value={patientData}
            onChange={(e) => setPatientData(e.target.value)}
            placeholder="Enter patient notes, diagnosis, medications, or biomarkers..."
            rows={10}
            disabled={isProcessing}
            spellCheck="false"
          />
        </div>

        <div className="example-actions">
          <span className="example-label">Load Example:</span>
          <button type="button" className="pill-btn" onClick={() => setPatientData(EXAMPLES.parkinsons)}>Parkinson's</button>
          <button type="button" className="pill-btn" onClick={() => setPatientData(EXAMPLES.alzheimers)}>Alzheimer's</button>
        </div>

        <button
          type="submit"
          className={`btn-primary init-btn ${isProcessing ? 'loading-pulse' : ''}`}
          disabled={isProcessing}
        >
          {isProcessing ? (
            <>
              <Activity className="spinner" size={20} />
              <span>Extracting Entities...</span>
            </>
          ) : (
            <>
              <Sparkles className="icon-glow" size={20} />
              <span>Initialize Discovery Graph</span>
            </>
          )}
        </button>
      </form>

      <div className="panel-footer">
        <div className="health-dot"></div>
        <span>NLP Engine Ready</span>
      </div>
    </div>
  );
}
