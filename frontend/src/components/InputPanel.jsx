import React, { useState, useRef } from 'react';
import { Bot, Activity, BrainCircuit, Sparkles, FileText, Plus, X, Upload } from 'lucide-react';
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

export default function InputPanel({ onSubmit, isProcessing, heroMode }) {
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

    // Construct the unstructured text the backend expects
    let combined = [];
    if (age) combined.push(`Age: ${age}`);
    if (sex !== "Unknown") combined.push(`Sex: ${sex}`);
    if (symptoms.length > 0) combined.push(`Symptoms: ${symptoms.join(", ")}`);
    if (report) combined.push(`\n${report}`);

    onSubmit(combined.join("\n"));
  };

  return (
    <div className={`input-panel glass-panel ${heroMode ? 'hero' : 'sidebar'}`}>
      <div className="panel-header">
        <div className="icon-wrapper">
          <BrainCircuit className="icon-cyan" size={heroMode ? 36 : 28} />
        </div>
        <div>
          <h2>Patient Intelligence</h2>
          <span className="subtitle-badge">Agentic Extraction</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="input-form">

        <div className="form-row">
          <div className="form-group half">
            <label>Age</label>
            <input
              type="number"
              value={age}
              onChange={e => setAge(e.target.value)}
              placeholder="e.g. 65"
              disabled={isProcessing}
            />
          </div>
          <div className="form-group half">
            <label>Sex</label>
            <select value={sex} onChange={e => setSex(e.target.value)} disabled={isProcessing}>
              <option value="Unknown">Unknown</option>
              <option value="Male">Male</option>
              <option value="Female">Female</option>
              <option value="Other">Other</option>
            </select>
          </div>
        </div>

        <div className="form-group">
          <label>Symptoms</label>
          <div className="symptom-input-group">
            <input
              type="text"
              value={symptomInput}
              onChange={e => setSymptomInput(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && handleSymptomAdd(e)}
              placeholder="Add symptom and press Enter..."
              disabled={isProcessing}
            />
            <button type="button" className="add-btn" onClick={handleSymptomAdd} disabled={isProcessing}>
              <Plus size={16} />
            </button>
          </div>
          {symptoms.length > 0 && (
            <div className="symptom-chips">
              {symptoms.map(s => (
                <span key={s} className="chip">
                  {s} <X size={12} className="chip-remove" onClick={() => removeSymptom(s)} />
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="form-group flex-grow textarea-group">
          <div className="textarea-header">
            <label>Clinical Notes</label>
            <button
              type="button"
              className="upload-btn"
              onClick={() => fileInputRef.current?.click()}
              disabled={isProcessing}
            >
              <Upload size={14} /> Upload TXT
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
            placeholder="Enter patient narrative, diagnosis, medications, or lab results..."
            disabled={isProcessing}
            spellCheck="false"
          />
        </div>

        <div className="example-actions">
          <span className="example-label">Examples:</span>
          <button type="button" className="pill-btn" onClick={() => loadExample('parkinsons')}>Parkinson's</button>
          <button type="button" className="pill-btn" onClick={() => loadExample('alzheimers')}>Alzheimer's</button>
        </div>

        <button
          type="submit"
          className={`btn-primary init-btn ${isProcessing ? 'loading-pulse' : ''}`}
          disabled={isProcessing}
        >
          {isProcessing ? (
            <>
              <Activity className="spinner" size={20} />
              <span>Analyzing Patient Data...</span>
            </>
          ) : (
            <>
              <Sparkles className="icon-glow" size={20} />
              <span>Generate Cure Graph</span>
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
