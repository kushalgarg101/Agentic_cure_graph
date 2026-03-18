import React, { useState, useRef } from 'react';
import { BrainCircuit, Sparkles, Activity, Plus, X, Upload } from 'lucide-react';
import './InputPanel.css';

const EXAMPLES = {
  parkinsons: {
    age: "68",
    sex: "Male",
    symptoms: ["Resting tremor", "bradykinesia", "rigidity"],
    report: "Patient with 3-year history of progressive motor symptoms. Recent bloodwork shows elevated inflammation. Currently on Metformin for comorbid Type 2 Diabetes. GBA1 mutation confirmed."
  },
  alzheimers: {
    age: "72",
    sex: "Female",
    symptoms: ["Memory loss", "confusion", "disorientation"],
    report: "Patient exhibiting significant short-term memory decline over the past year. PET scan revealed amyloid plaques. Prescribed Donepezil."
  }
};

export default function InputPanel({ onSubmit, isProcessing }) {
  const [age, setAge] = useState("");
  const [sex, setSex] = useState("Unknown");
  const [report, setReport] = useState("");
  const [symptoms, setSymptoms] = useState([]);
  const [symptomInput, setSymptomInput] = useState("");
  const fileInputRef = useRef(null);

  const handleSymptomAdd = (e) => {
    e.preventDefault();
    if (symptomInput.trim() && !symptoms.includes(symptomInput.trim())) {
      setSymptoms([...symptoms, symptomInput.trim()]);
      setSymptomInput("");
    }
  };

  const removeSymptom = (s) => {
    setSymptoms(symptoms.filter(sym => sym !== s));
  };

  const loadExample = (type) => {
    const data = EXAMPLES[type];
    setAge(data.age);
    setSex(data.sex);
    setSymptoms([...data.symptoms]);
    setReport(data.report);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      setReport(event.target.result);
    };
    reader.readAsText(file);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!report.trim() && symptoms.length === 0) return;

    let combined = [];
    if (age) combined.push(`Age: ${age}`);
    if (sex !== "Unknown") combined.push(`Sex: ${sex}`);
    if (symptoms.length > 0) combined.push(`Symptoms: ${symptoms.join(", ")}`);
    if (report) combined.push(`\n${report}`);

    onSubmit(combined.join("\n"));
  };

  return (
    <div className="input-panel">
      {/* Header */}
      <div className="ip-header">
        <div className="ip-header-icon">
          <BrainCircuit size={20} />
        </div>
        <div className="ip-header-text">
          <h2>Patient Input</h2>
          <span className="ip-header-sub">Structured extraction</span>
        </div>
      </div>

      <div className="ip-divider" />

      {/* Form */}
      <form onSubmit={handleSubmit} className="ip-form">

        {/* Demographics Section */}
        <div className="ip-section">
          <label className="ip-section-label">Demographics</label>
          <div className="ip-row">
            <div className="ip-field">
              <label>Age</label>
              <input
                type="number"
                value={age}
                onChange={e => setAge(e.target.value)}
                placeholder="e.g. 65"
                disabled={isProcessing}
              />
            </div>
            <div className="ip-field">
              <label>Sex</label>
              <select value={sex} onChange={e => setSex(e.target.value)} disabled={isProcessing}>
                <option value="Unknown">Unknown</option>
                <option value="Male">Male</option>
                <option value="Female">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
          </div>
        </div>

        <div className="ip-divider" />

        {/* Symptoms Section */}
        <div className="ip-section">
          <label className="ip-section-label">Symptoms</label>
          <div className="ip-symptom-input-row">
            <input
              type="text"
              value={symptomInput}
              onChange={e => setSymptomInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSymptomAdd(e)}
              placeholder="Type and press Enter..."
              disabled={isProcessing}
            />
            <button type="button" className="ip-add-btn" onClick={handleSymptomAdd} disabled={isProcessing}>
              <Plus size={16} />
            </button>
          </div>
          {symptoms.length > 0 && (
            <div className="ip-chips">
              {symptoms.map(s => (
                <span key={s} className="ip-chip">
                  {s}
                  <button type="button" className="ip-chip-x" onClick={() => removeSymptom(s)}>
                    <X size={12} />
                  </button>
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="ip-divider" />

        {/* Clinical Notes Section */}
        <div className="ip-section ip-section-grow">
          <div className="ip-section-head">
            <label className="ip-section-label">Clinical Notes</label>
            <button
              type="button"
              className="ip-upload-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={isProcessing}
            >
              <Upload size={13} />
              <span>Upload .txt</span>
            </button>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".txt"
              style={{ display: 'none' }}
            />
          </div>
          <textarea
            value={report}
            onChange={(e) => setReport(e.target.value)}
            placeholder="Patient narrative, diagnosis, medications, lab results..."
            disabled={isProcessing}
            spellCheck="false"
            className="ip-textarea"
          />
        </div>

        {/* Examples */}
        <div className="ip-examples">
          <span className="ip-examples-label">Quick fill</span>
          <div className="ip-examples-pills">
            <button type="button" className="ip-pill" onClick={() => loadExample('parkinsons')}>
              Parkinson's
            </button>
            <button type="button" className="ip-pill" onClick={() => loadExample('alzheimers')}>
              Alzheimer's
            </button>
          </div>
        </div>

        {/* Submit */}
        <button
          type="submit"
          className={`ip-submit ${isProcessing ? 'ip-submit-loading' : ''}`}
          disabled={isProcessing}
        >
          {isProcessing ? (
            <>
              <Activity className="ip-spinner" size={18} />
              <span>Analyzing...</span>
            </>
          ) : (
            <>
              <Sparkles size={18} />
              <span>Generate Cure Graph</span>
            </>
          )}
        </button>
      </form>

      {/* Footer */}
      <div className="ip-footer">
        <div className="ip-footer-dot" />
        <span>Engine ready</span>
      </div>
    </div>
  );
}
