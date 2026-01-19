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
