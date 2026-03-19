import React, { useRef, useState } from 'react';
import {
  Activity,
  BrainCircuit,
  FileJson,
  FlaskConical,
  Sparkles,
  Upload,
  User,
  Stethoscope,
  Zap,
  TestTube2,
  ListPlus
} from 'lucide-react';
import './InputPanel.css';

const STRUCTURED_EXAMPLES = {
  parkinsons: {
    patientId: 'PAT-001',
    ageRange: '65-70',
    sex: 'male',
    diagnoses: "Parkinson's Disease",
    symptoms: 'Resting tremor\nBradykinesia\nRigidity',
    biomarkers: 'DaTSCAN: reduced uptake\nElevated inflammation',
    medications: 'Levodopa/Carbidopa 100/25 mg TID\nMetformin',
    reportText: 'Three-year history of progressive motor symptoms. Narrative mentions activated microglia and elevated CRP. GBA1 mutation confirmed.',
  },
  alzheimers: {
    patientId: 'PAT-002',
    ageRange: '70-79',
    sex: 'female',
    diagnoses: "Alzheimer's Disease",
    symptoms: 'Short-term memory loss\nDisorientation\nWord-finding difficulty',
    biomarkers: 'Amyloid PET: positive\nAPOE4 genotype\nCSF tau elevated',
    medications: 'Donepezil 10mg daily',
    reportText: 'Progressive cognitive decline over 18 months with biomarker-confirmed amyloid burden and elevated tau.',
  },
};

const FHIR_EXAMPLE = JSON.stringify(
  {
    record: {
      id: 'FHIR-001',
      gender: 'male',
      age_range: '65-70',
      condition: [
        { code: { text: "Parkinson's Disease" } },
        'Hypertension',
      ],
      observations: [
        { display: 'DaTSCAN: reduced uptake in putamen' },
        'UPDRS Motor Score: 32',
      ],
      medications: [
        { display: 'Levodopa/Carbidopa 100/25 mg TID' },
      ],
      symptoms: ['Resting tremor', 'Bradykinesia'],
      note: 'Clinical notes mention gait instability and elevated inflammation.',
    },
  },
  null,
  2,
);

function splitTerms(raw) {
  return raw.split(/\r?\n|,/).map((item) => item.trim()).filter(Boolean);
}

export default function InputPanel({ onSubmit, isProcessing }) {
  const [inputMode, setInputMode] = useState('structured');
  const [evidenceMode, setEvidenceMode] = useState('offline');
  const [patientId, setPatientId] = useState('PAT-1002');
  const [ageRange, setAgeRange] = useState('60-69');
  const [sex, setSex] = useState('unknown');
  const [diagnoses, setDiagnoses] = useState('');
  const [symptoms, setSymptoms] = useState('');
  const [biomarkers, setBiomarkers] = useState('');
  const [medications, setMedications] = useState('');
  const [reportText, setReportText] = useState('');
  const [fhirText, setFhirText] = useState(FHIR_EXAMPLE);
  const fileInputRef = useRef(null);

  const loadStructuredExample = (key) => {
    const example = STRUCTURED_EXAMPLES[key];
    setInputMode('structured');
    setPatientId(example.patientId);
    setAgeRange(example.ageRange);
    setSex(example.sex);
    setDiagnoses(example.diagnoses);
    setSymptoms(example.symptoms);
    setBiomarkers(example.biomarkers);
    setMedications(example.medications);
    setReportText(example.reportText);
  };

  const loadFhirExample = () => {
    setInputMode('fhir');
    setFhirText(FHIR_EXAMPLE);
  };

  const handleFileUpload = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (loadEvent) => {
      const content = String(loadEvent.target?.result || '');
      if (inputMode === 'fhir') {
        setFhirText(content);
      } else {
        setReportText(content);
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = (event) => {
    event.preventDefault();

    if (inputMode === 'fhir') {
      if (!fhirText.trim()) return;
      onSubmit({ mode: 'fhir', fhirText, evidenceMode });
      return;
    }

    const payload = {
      patient_case: {
        patient_id: patientId.trim() || 'patient-record',
        age_range: ageRange.trim() || 'unknown',
        sex,
        diagnoses: splitTerms(diagnoses),
        symptoms: splitTerms(symptoms),
        biomarkers: splitTerms(biomarkers),
        medications: splitTerms(medications),
      },
      report_text: reportText.trim(),
      evidence_mode: evidenceMode,
      with_ai: false,
      input_format: 'structured',
    };

    const hasStructuredContent =
      payload.patient_case.diagnoses.length > 0 ||
      payload.patient_case.symptoms.length > 0 ||
      payload.patient_case.biomarkers.length > 0 ||
      payload.patient_case.medications.length > 0 ||
      payload.report_text.length > 0;

    if (!hasStructuredContent) return;
    onSubmit({ mode: 'structured', payload });
  };

  return (
    <div className="input-panel">
      <div className="ip-header">
        <div className="ip-header-icon">
          <BrainCircuit size={24} strokeWidth={1.5} />
        </div>
        <div className="ip-header-text">
          <h2>Cure Graph</h2>
          <span className="ip-header-sub">Biomedical Reasoning</span>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="ip-form">
        <div className="ip-section">
          <div className="ip-mode-toggle">
            <button
              type="button"
              className={inputMode === 'structured' ? 'ip-mode-active' : ''}
              onClick={() => setInputMode('structured')}
              disabled={isProcessing}
            >
              <FlaskConical size={16} /> Structured
            </button>
            <button
              type="button"
              className={inputMode === 'fhir' ? 'ip-mode-active' : ''}
              onClick={() => setInputMode('fhir')}
              disabled={isProcessing}
            >
              <FileJson size={16} /> FHIR Source
            </button>
          </div>
        </div>

        <div className="ip-section">
          <div className="ip-section-head">
             <div className="ip-section-title">
                <Zap size={14} /> Analysis Scope
             </div>
          </div>
          <div className="ip-field">
            <select
              value={evidenceMode}
              onChange={(event) => setEvidenceMode(event.target.value)}
              disabled={isProcessing}
            >
              <option value="offline">Offline Repository (Fast)</option>
              <option value="hybrid">Live Agents (PubMed/ChEMBL)</option>
            </select>
          </div>
        </div>

        {inputMode === 'structured' ? (
          <>
            <div className="ip-section">
              <div className="ip-section-head">
                 <div className="ip-section-title">
                    <User size={14} /> Demographics
                 </div>
              </div>
              <div className="ip-row" style={{ marginBottom: '8px' }}>
                <div className="ip-field">
                  <input
                    type="text"
                    value={patientId}
                    onChange={(event) => setPatientId(event.target.value)}
                    placeholder="Patient ID (e.g. PAT-1002)"
                    disabled={isProcessing}
                  />
                </div>
              </div>
              <div className="ip-row">
                <div className="ip-field">
                  <input
                    type="text"
                    value={ageRange}
                    onChange={(event) => setAgeRange(event.target.value)}
                    placeholder="Age (60-69)"
                    disabled={isProcessing}
                  />
                </div>
                <div className="ip-field">
                  <select
                    value={sex}
                    onChange={(event) => setSex(event.target.value)}
                    disabled={isProcessing}
                  >
                    <option value="unknown">Sex</option>
                    <option value="male">Male</option>
                    <option value="female">Female</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="ip-section">
              <div className="ip-section-head">
                 <div className="ip-section-title">
                    <Stethoscope size={14} /> Diagnostics
                 </div>
              </div>
              <div className="ip-field">
                <input
                  type="text"
                  value={diagnoses}
                  onChange={(event) => setDiagnoses(event.target.value)}
                  placeholder="Primary Diagnoses (comma sep)"
                  disabled={isProcessing}
                />
              </div>
              <div className="ip-field">
                <textarea
                  value={symptoms}
                  onChange={(event) => setSymptoms(event.target.value)}
                  placeholder="Clinical symptoms..."
                  disabled={isProcessing}
                  className="ip-textarea ip-textarea-compact"
                />
              </div>
            </div>

            <div className="ip-section">
              <div className="ip-section-head">
                 <div className="ip-section-title">
                    <TestTube2 size={14} /> Biomarkers & Meds
                 </div>
              </div>
              <div className="ip-field">
                <textarea
                  value={biomarkers}
                  onChange={(event) => setBiomarkers(event.target.value)}
                  placeholder="Genetic or lab biomarkers..."
                  disabled={isProcessing}
                  className="ip-textarea ip-textarea-compact"
                />
              </div>
              <div className="ip-field">
                <textarea
                  value={medications}
                  onChange={(event) => setMedications(event.target.value)}
                  placeholder="Current medications..."
                  disabled={isProcessing}
                  className="ip-textarea ip-textarea-compact"
                />
              </div>
            </div>

            <div className="ip-section ip-section-grow">
              <div className="ip-section-head">
                <div className="ip-section-title">
                    <ListPlus size={14} /> Clinical Notes
                </div>
                <button
                  type="button"
                  className="ip-upload-btn"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isProcessing}
                >
                  <Upload size={12} /> Upload
                </button>
              </div>
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".txt"
                style={{ display: 'none' }}
              />
              <textarea
                value={reportText}
                onChange={(event) => setReportText(event.target.value)}
                placeholder="Paste narrative summary or consultation notes here. The agent will extract relevant context..."
                disabled={isProcessing}
                spellCheck="false"
                className="ip-textarea ip-textarea-large"
              />
            </div>
          </>
        ) : (
          <div className="ip-section ip-section-grow">
            <div className="ip-section-head">
                <div className="ip-section-title">
                    <FileJson size={14} /> FHIR Payload
                </div>
              <button
                type="button"
                className="ip-upload-btn"
                onClick={() => fileInputRef.current?.click()}
                disabled={isProcessing}
              >
                <Upload size={12} /> Upload JSON
              </button>
            </div>
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileUpload}
              accept=".json,.txt"
              style={{ display: 'none' }}
            />
            <textarea
              value={fhirText}
              onChange={(event) => setFhirText(event.target.value)}
              placeholder='{"resourceType": "Patient", ...}'
              disabled={isProcessing}
              spellCheck="false"
              className="ip-textarea ip-textarea-code"
            />
          </div>
        )}

        <div className="ip-examples">
          <div className="ip-examples-pills">
            <button
              type="button"
              className="ip-pill"
              onClick={() => loadStructuredExample('parkinsons')}
            >
              <Zap size={10} /> Parkinson's Case
            </button>
            <button
              type="button"
              className="ip-pill"
              onClick={() => loadStructuredExample('alzheimers')}
            >
              <Zap size={10} /> Alzheimer's Case
            </button>
            <button type="button" className="ip-pill" onClick={loadFhirExample}>
              <Zap size={10} /> FHIR Example
            </button>
          </div>
        </div>

        <button
          type="submit"
          className={`ip-submit ${isProcessing ? 'ip-submit-loading' : ''}`}
          disabled={isProcessing}
        >
          {isProcessing ? (
            <>
              <Activity className="ip-spinner" size={20} />
              <span>Analyzing Network...</span>
            </>
          ) : (
            <>
              <Sparkles size={20} />
              <span>Generate Cure Graph</span>
            </>
          )}
        </button>
      </form>

      <div className="ip-footer">
        <div className="ip-footer-dot" />
        <span>Secure Local Connection</span>
      </div>
    </div>
  );
}
