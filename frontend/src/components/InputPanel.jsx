import React, { useState } from 'react';
import { Bot, Activity, BrainCircuit } from 'lucide-react';
import './InputPanel.css';

export default function InputPanel({ onSubmit, isProcessing }) {
  const [patientData, setPatientData] = useState(
    "Diagnosis: Parkinson's disease\nBiomarker: elevated inflammation\nMedication: Metformin\nAge: 68\nSymptoms: Resting tremor, bradykinesia."
  );

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!patientData.trim()) return;
    onSubmit(patientData);
  };

  return (
    <div className="input-panel glass-panel">
      <div className="panel-header">
        <BrainCircuit className="icon-cyan" size={24} />
        <h2>Agentic Patient Intelligence</h2>
      </div>
      
      <form onSubmit={handleSubmit} className="input-form">
        <label htmlFor="patient-data">Synthetic Patient Narrative</label>
        <textarea
          id="patient-data"
          value={patientData}
          onChange={(e) => setPatientData(e.target.value)}
          placeholder="Enter patient notes, diagnosis, medications, or biomarkers..."
          rows={8}
          disabled={isProcessing}
        />
        
        <button 
          type="submit" 
          className={`btn-primary ${isProcessing ? 'loading-pulse' : ''}`}
          disabled={isProcessing}
        >
          {isProcessing ? (
            <>
              <Activity className="spinner" size={18} />
              Extracting Entities...
            </>
          ) : (
            <>
              <Bot size={18} />
              Initialize Discovery Graph
            </>
          )}
        </button>
      </form>
    </div>
  );
}
