import React, { useState, useMemo } from "react";
import "./App.css";

const PAINTERS = [
  "Van Gogh","Monet","Picasso","Da Vinci","Rembrandt","Matisse","Kandinsky",
  "Hokusai","Yayoi Kusama","Frida Kahlo","Salvador Dali","Rothko","Pollock",
  "Chagall","Basquiat","Haring","Georgia O'Keeffe","Turner","Seurat","Escher"
];

const MODELS = [
  "gpt-4o-mini",
  "gpt-4.1-mini",
  "gemini-2.5-flash",
  "gemini-3-flash-preview",
];

function App() {
  const [theme, setTheme] = useState("light");
  const [lang, setLang] = useState("en");

  const [openaiKey, setOpenaiKey] = useState("");
  const [geminiKey, setGeminiKey] = useState("");
  const [showKeys, setShowKeys] = useState(false);

  const [selectedPainter, setSelectedPainter] = useState(PAINTERS[0]);

  const [status, setStatus] = useState("Idle");
  const [error, setError] = useState("");

  // Submission state
  const [submissionText, setSubmissionText] = useState("");
  const [submissionFile, setSubmissionFile] = useState(null);
  const [submissionModel, setSubmissionModel] = useState(MODELS[0]);
  const [submissionResult, setSubmissionResult] = useState("");

  // Checklist state
  const [checklistText, setChecklistText] = useState("");
  const [checklistFile, setChecklistFile] = useState(null);
  const [checklistModel, setChecklistModel] = useState(MODELS[0]);
  const [checklistResult, setChecklistResult] = useState("");

  // Review state
  const [reviewSubmission, setReviewSubmission] = useState("");
  const [reviewChecklist, setReviewChecklist] = useState("");
  const [reviewModel, setReviewModel] = useState(MODELS[0]);
  const [reviewResult, setReviewResult] = useState("");

  const bodyClass = useMemo(
    () => (theme === "dark" ? "app-root theme-dark" : "app-root theme-light"),
    [theme]
  );

  async function handleSaveKeys() {
    setStatus("Saving keys");
    setError("");
    try {
      const res = await fetch("/set_api_keys", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          openai: openaiKey || undefined,
          gemini: geminiKey || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Failed to save keys");
      }
      setStatus(data.status || "saved");
    } catch (e) {
      setError(e.message);
      setStatus("Error");
    }
  }

  function buildFormData(fields) {
    const formData = new FormData();
    Object.entries(fields).forEach(([k, v]) => {
      if (v !== undefined && v !== null) {
        formData.append(k, v);
      }
    });
    return formData;
  }

  async function postFormData(url, formData) {
    const res = await fetch(url, {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `Request failed: ${url}`);
    }
    return data;
  }

  async function handleTransformSubmission() {
    setStatus("Transforming submission");
    setError("");
    try {
      const formData = buildFormData({
        pasted: submissionText,
        model: submissionModel,
        file: submissionFile || undefined,
      });
      const data = await postFormData("/transform_submission", formData);
      setSubmissionResult(data.result || "");
      setStatus("Idle");
    } catch (e) {
      setError(e.message);
      setStatus("Error");
    }
  }

  async function handleTransformChecklist() {
    setStatus("Transforming checklist");
    setError("");
    try {
      const formData = buildFormData({
        pasted: checklistText,
        model: checklistModel,
        file: checklistFile || undefined,
      });
      const data = await postFormData("/transform_checklist", formData);
      setChecklistResult(data.result || "");
      setStatus("Idle");
    } catch (e) {
      setError(e.message);
      setStatus("Error");
    }
  }

  async function handleRunReview() {
    setStatus("Running review");
    setError("");
    try {
      const submission = reviewSubmission || submissionResult;
      const checklist = reviewChecklist || checklistResult;
      const formData = buildFormData({
        submission,
        checklist,
        model: reviewModel,
      });
      const data = await postFormData("/run_review", formData);
      setReviewResult(data.result || "");
      setStatus("Idle");
    } catch (e) {
      setError(e.message);
      setStatus("Error");
    }
  }

  function handleJackpot() {
    const idx = Math.floor(Math.random() * PAINTERS.length);
    setSelectedPainter(PAINTERS[idx]);
  }

  function handleApplyStyle() {
    alert(`Style applied: ${selectedPainter}`);
  }

  return (
    <div className={bodyClass}>
      <div className="app">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="flex-between">
            <h3>Settings</h3>
            <div className="selectors">
              <select
                value={theme}
                onChange={(e) => setTheme(e.target.value)}
              >
                <option value="light">light</option>
                <option value="dark">dark</option>
              </select>
              <select
                value={lang}
                onChange={(e) => {
                  setLang(e.target.value);
                  alert("Language switcher placeholder");
                }}
              >
                <option value="en">English</option>
                <option value="zh">繁體中文</option>
              </select>
            </div>
          </div>

          <label>API Keys (stored server-side)</label>
          <div className="muted small">
            Keys from environment will be used and hidden.
          </div>

          <input
            type={showKeys ? "text" : "password"}
            placeholder="OpenAI API Key"
            value={openaiKey}
            onChange={(e) => setOpenaiKey(e.target.value)}
          />
          <input
            type={showKeys ? "text" : "password"}
            placeholder="Gemini API Key"
            value={geminiKey}
            onChange={(e) => setGeminiKey(e.target.value)}
          />

          <div className="row">
            <button className="btn" onClick={handleSaveKeys}>
              Save Keys
            </button>
            <button
              className="btn btn-secondary"
              onClick={() => setShowKeys((v) => !v)}
            >
              {showKeys ? "Hide" : "Show"}
            </button>
          </div>

          <hr />

          <label>Painter Styles (pick or Jackpot)</label>
          <div className="painters">
            {PAINTERS.map((p) => (
              <div
                key={p}
                className={
                  "painter" + (p === selectedPainter ? " painter-selected" : "")
                }
                onClick={() => setSelectedPainter(p)}
              >
                {p}
              </div>
            ))}
          </div>
          <div className="row">
            <button className="btn" onClick={handleJackpot}>
              Jackpot
            </button>
            <button className="btn" onClick={handleApplyStyle}>
              Apply
            </button>
          </div>

          <hr />

          <div className="muted small">
            Status: <span>{status}</span>
          </div>
          {error && (
            <div className="error small" style={{ marginTop: "8px" }}>
              Error: {error}
            </div>
          )}
        </aside>

        {/* Main content */}
        <main className="main">
          <h1>WOW 510(k) Assistant (React UI)</h1>

          {/* Transform submission */}
          <section className="panel">
            <label>Paste Submission (text/markdown) or upload PDF</label>
            <textarea
              value={submissionText}
              onChange={(e) => setSubmissionText(e.target.value)}
              placeholder="Paste submission here..."
            />
            <input
              type="file"
              accept=".pdf,.txt,.md,.markdown"
              onChange={(e) => setSubmissionFile(e.target.files?.[0] || null)}
            />
            <div className="row">
              <select
                value={submissionModel}
                onChange={(e) => setSubmissionModel(e.target.value)}
              >
                {MODELS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <button className="btn" onClick={handleTransformSubmission}>
                Transform Submission
              </button>
            </div>
            <div className="result">
              {submissionResult || <span className="muted">No result yet.</span>}
            </div>
          </section>

          <hr />

          {/* Transform checklist */}
          <section className="panel">
            <label>Paste Checklist or upload CSV</label>
            <textarea
              value={checklistText}
              onChange={(e) => setChecklistText(e.target.value)}
            />
            <input
              type="file"
              accept=".csv,.txt,.md,.markdown"
              onChange={(e) => setChecklistFile(e.target.files?.[0] || null)}
            />
            <div className="row">
              <select
                value={checklistModel}
                onChange={(e) => setChecklistModel(e.target.value)}
              >
                {MODELS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <button className="btn" onClick={handleTransformChecklist}>
                Transform Checklist
              </button>
            </div>
            <div className="result">
              {checklistResult || <span className="muted">No result yet.</span>}
            </div>
          </section>

          <hr />

          {/* Run review */}
          <section className="panel">
            <label>Run Review</label>
            <textarea
              placeholder="Paste organized submission markdown (or leave blank to use the last result)"
              value={reviewSubmission}
              onChange={(e) => setReviewSubmission(e.target.value)}
            />
            <textarea
              placeholder="Paste organized checklist markdown (or leave blank to use the last result)"
              value={reviewChecklist}
              onChange={(e) => setReviewChecklist(e.target.value)}
            />
            <div className="row">
              <select
                value={reviewModel}
                onChange={(e) => setReviewModel(e.target.value)}
              >
                {MODELS.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
              <button className="btn" onClick={handleRunReview}>
                Run Review
              </button>
            </div>
            <div className="result">
              {reviewResult || <span className="muted">No result yet.</span>}
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}

export default App;
