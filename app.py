from flask import Flask, request, render_template_string, jsonify, send_file
import os
import io
import random
import json
from collections import Counter

try:
    import openai
except Exception:
    openai = None

# Use latest google.generativeai package
try:
    import google.generativeai as genai
except Exception:
    genai = None

try:
    import fitz
except Exception:
    fitz = None

app = Flask(__name__)

# In-memory API keys store (do not expose values)
API_KEYS = {
    "openai": os.getenv("OPENAI_API_KEY") or "",
    "gemini": os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "",
}

PAINTERS = [
    "Van Gogh","Monet","Picasso","Da Vinci","Rembrandt","Matisse","Kandinsky",
    "Hokusai","Yayoi Kusama","Frida Kahlo","Salvador Dali","Rothko","Pollock",
    "Chagall","Basquiat","Haring","Georgia O'Keeffe","Turner","Seurat","Escher"
]

# You can keep this template if you still want a non-React fallback page.
INDEX_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>WOW 510(k) Assistant (Legacy UI)</title>
</head>
<body>
  <h1>Backend is running.</h1>
  <p>This is the legacy Flask template. The main UI is now provided by the React frontend.</p>
</body>
</html>
"""

def extract_text_from_pdf_stream(stream):
    if fitz is None:
        return ""
    doc = fitz.open(stream=stream.read(), filetype='pdf')
    pages = []
    for p in doc:
        pages.append(p.get_text())
    return "\n\n".join(pages)


def call_llm(model, prompt, max_tokens=1024, temperature=0.2):
    """
    Unified LLM call helper.
    - OpenAI: supports both new and legacy Python SDKs.
    - Gemini: uses modern `google.generativeai` practices.
    """
    provider = 'openai' if model.startswith('gpt') else ('gemini' if model.startswith('gemini') else 'openai')

    # ---------- OpenAI branch ----------
    if provider == 'openai':
        if openai is None:
            return {'error': 'openai package not installed on server. Install with: pip install openai'}
        key = API_KEYS.get('openai') or os.getenv('OPENAI_API_KEY')
        if not key:
            return {'error': 'OpenAI API key not set.'}
        os.environ['OPENAI_API_KEY'] = key

        try:
            # New-style OpenAI client if available
            if hasattr(openai, 'OpenAI'):
                try:
                    client = openai.OpenAI(api_key=key)
                except Exception:
                    client = openai.OpenAI()

                # Prefer chat.completions
                if hasattr(client, 'chat') and hasattr(client.chat, 'completions') and hasattr(client.chat.completions, 'create'):
                    resp = client.chat.completions.create(
                        model=model,
                        messages=[{'role': 'user', 'content': prompt}],
                        max_tokens=max_tokens,
                        temperature=temperature,
                    )
                    try:
                        message = resp.choices[0].message
                        text = message['content'] if isinstance(message, dict) else getattr(message, 'content', None)
                    except Exception:
                        text = getattr(resp.choices[0], 'text', None) or getattr(resp, 'output_text', None)
                    return {'text': text}

                # Fallback: responses API if available
                if hasattr(client, 'responses') and hasattr(client.responses, 'create'):
                    resp = client.responses.create(
                        model=model,
                        input=prompt,
                        max_output_tokens=max_tokens,
                    )
                    text = getattr(resp, 'output_text', None)
                    if not text:
                        try:
                            parts = []
                            for item in getattr(resp, 'output', []) or []:
                                if isinstance(item, dict):
                                    content = item.get('content')
                                    if isinstance(content, list):
                                        for c in content:
                                            if isinstance(c, dict) and 'text' in c:
                                                parts.append(c['text'])
                                            elif isinstance(c, str):
                                                parts.append(c)
                                    elif isinstance(content, str):
                                        parts.append(content)
                                else:
                                    parts.append(str(item))
                            if parts:
                                text = '\n'.join(parts)
                        except Exception:
                            text = str(resp)
                    if not text:
                        text = str(resp)
                    return {'text': text}

            # Legacy ChatCompletion API
            if hasattr(openai, 'ChatCompletion'):
                openai.api_key = key
                resp = openai.ChatCompletion.create(
                    model=model,
                    messages=[{'role': 'user', 'content': prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                choice = resp.choices[0]
                if hasattr(choice, 'message'):
                    return {'text': choice.message['content']}
                return {'text': choice.text}

            return {'error': 'Installed openai package does not expose a supported API (ChatCompletion or OpenAI client). Try: OPENAI migrate or adjust SDK version.'}
        except Exception as e:
            msg = str(e)
            if 'ChatCompletion' in msg or 'chat' in msg.lower():
                msg += ' — If you recently upgraded the OpenAI SDK, try: OPENAI migrate'
            return {'error': msg}

    # ---------- Gemini branch (modern google.generativeai) ----------
    if provider == 'gemini':
        if genai is None:
            return {'error': 'google.generativeai not installed. Install with: pip install google-generativeai'}
        key = API_KEYS.get('gemini') or os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if not key:
            return {'error': 'Gemini API key not set. Provide GEMINI_API_KEY or GOOGLE_API_KEY.'}

        try:
            genai.configure(api_key=key)

            # You can adjust generation_config as needed
            generation_config = {
                "temperature": float(temperature),
                "max_output_tokens": int(max_tokens),
            }

            model_name = model  # e.g., "gemini-1.5-flash", "gemini-1.5-pro"
            generative_model = genai.GenerativeModel(model_name)

            response = generative_model.generate_content(
                prompt,
                generation_config=generation_config,
            )

            text = getattr(response, "text", None)
            if not text and hasattr(response, "candidates"):
                try:
                    parts = []
                    for cand in response.candidates:
                        for part in getattr(cand, "content", {}).parts:
                            if hasattr(part, "text"):
                                parts.append(part.text)
                    if parts:
                        text = "\n".join(parts)
                except Exception:
                    text = None

            if not text:
                text = str(response)

            return {'text': text}
        except Exception as e:
            return {'error': f'Gemini error: {e}'}

    return {'error': 'Unsupported model/provider.'}


@app.route('/')
def index():
    # Serve a minimal page here; React will typically run on its own dev server.
    return render_template_string(INDEX_HTML)


@app.route('/set_api_keys', methods=['POST'])
def set_api_keys():
    data = request.get_json() or {}
    if 'openai' in data and data['openai']:
        API_KEYS['openai'] = data['openai']
    if 'gemini' in data and data['gemini']:
        API_KEYS['gemini'] = data['gemini']
    return jsonify({'status': 'saved'})


@app.route('/transform_submission', methods=['POST'])
def transform_submission():
    pasted = request.form.get('pasted', '')
    model = request.form.get('model') or 'gpt-4o-mini'
    f = request.files.get('file')
    text = pasted
    if f:
        fname = f.filename.lower()
        if fname.endswith('.pdf'):
            text = extract_text_from_pdf_stream(f.stream)
        else:
            try:
                text = f.stream.read().decode('utf-8')
            except Exception:
                text = ''
    prompt = (
        "Organize the following 510(k) submission into structured markdown "
        "with headings, summary, and checklist.\n\nSource:\n"
        f"{text[:3000]}"
    )
    res = call_llm(model, prompt)
    if 'text' in res:
        return jsonify({'result': res['text']})
    return jsonify({'error': res.get('error', 'unknown')}), 500


@app.route('/transform_checklist', methods=['POST'])
def transform_checklist():
    pasted = request.form.get('pasted', '')
    model = request.form.get('model') or 'gpt-4o-mini'
    f = request.files.get('file')
    text = pasted
    if f:
        try:
            text = f.stream.read().decode('utf-8')
        except Exception:
            text = ''
    prompt = (
        "Organize the following checklist into a clear markdown checklist "
        "grouped by sections.\n\nSource:\n"
        f"{text[:3000]}"
    )
    res = call_llm(model, prompt)
    if 'text' in res:
        return jsonify({'result': res['text']})
    return jsonify({'error': res.get('error', 'unknown')}), 500


@app.route('/run_review', methods=['POST'])
def run_review():
    submission = request.form.get('submission', '')
    checklist = request.form.get('checklist', '')
    model = request.form.get('model') or 'gpt-4o-mini'
    prompt = (
        "Using the checklist below, evaluate the submission and produce a "
        "structured review report with findings, recommended actions, and "
        "missing documents.\n\nCHECKLIST:\n"
        f"{checklist[:2000]}\n\nSUBMISSION:\n{submission[:8000]}"
    )
    res = call_llm(model, prompt)
    if 'text' in res:
        return jsonify({'result': res['text']})
    return jsonify({'error': res.get('error', 'unknown')}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
```

---

## 2. React-based front page for this backend

Below is a React single-page UI that talks directly to the existing Flask endpoints:

- `POST /set_api_keys` (JSON)
- `POST /transform_submission` (FormData)
- `POST /transform_checklist` (FormData)
- `POST /run_review` (FormData)

You can use Vite or Create React App; the code below assumes a typical `src/App.jsx` setup.

### 2.1 `src/App.jsx`

```jsx
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
