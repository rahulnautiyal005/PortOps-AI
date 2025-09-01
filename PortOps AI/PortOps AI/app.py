#!/usr/bin/env python3
import os
import json
import csv
import io
import math
from pathlib import Path
from typing import Dict, Any, List

# --- New library needed for text extraction ---
# pip install PyMuPDF
import fitz  # PyMuPDF

# --- Libraries needed ---
# pip install google-generativeai flask python-dotenv
from dotenv import load_dotenv
from flask import Flask, render_template, request, Response, session, redirect, url_for
from werkzeug.utils import secure_filename

import google.generativeai as genai

# ----------------------------- CONFIG ---------------------------------
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable not set.")
genai.configure(api_key=API_KEY)

BASE_DIR = Path(__file__).parent
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {'pdf', 'docx'}

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

LLM_MODEL = "gemini-2.5-flash" # Using a fast and efficient model

SOF_EXTRACTION_PROMPT = """
You are an expert AI assistant specializing in logistics and shipping documentation. Your task is to meticulously extract all port operations events from the provided 'Statement of Facts' (SoF) document, strictly following the conditions and edge cases below.

---

### Edge Case Handling Rules:
1. Data Structure: Store events in a structured list format inside a JSON object. Each event must include "event", "start_time", and "end_time". The top-level output must always be:
{
  "events": [
    { "event": ..., "start_time": ..., "end_time": ... }
  ]
}

2. Missing Start/End Times:
    - First, sort all events by start_time (if missing, then by end_time).
    - If start_time is missing, infer it from the previous event's end_time after sorting.
    - If end_time is missing, infer it from the next event's start_time.
    - Example:
      - Event A: 10:00-12:00, Event B: null - 14:00 → Event B start = 12:00.
      - Event A: 10:00 - 12:00, Event B: null - 11:00 → Event B start = 10:00.

3. Rest/Break Periods:
    - If a break period exists (e.g., Rest 12:00 - 14:00), include it as a separate event "event": "Rest period".
    - Ensure the next event does not start before the rest ends.
    - Example: Event A: 10:00 - 12:00, Rest: 12:00 - 14:00, Event B: null - 16:00 → Event B start = 14:00.

4. Arrival/Departure Times:
    - Do not include vessel arrival or departure times in the output.

5. Unreadable/Misprinted Data:
    - If times or events cannot be determined due to misprint/blurred text, skip them and add them separately under "unresolved_events" in the final JSON with only "event": ... and a note.
    - Example:
    {
      "unresolved_events": [
        { "event": "Some unreadable entry - please check manually" }
      ]
    }

6. Overlaps / Same Time Events:
    - If multiple events overlap or share the same timestamp, list all of them separately in the JSON.

7. Rules:
    - Do not output any event where start_time == end_time.
    - Never invent or guess times. If you cannot resolve, move the event to "unresolved_events".
    - Skip events explicitly marked “as per charter party (CP)”.
    - Never output false information. Skipping is allowed, fabrication is not.

---

### Output Format:
Always return valid JSON with this structure:

{
  "events": [
    {
      "event": "Cargo Loading Operation",
      "start_time": "2024-08-20 14:30",
      "end_time": "2024-08-21 02:00"
    },
    {
      "event": "Rest period",
      "start_time": "2024-08-21 02:00",
      "end_time": "2024-08-21 04:00"
    }
  ],
  "unresolved_events": [
    {
      "event": "Unreadable entry at page 5 - please check manually"
    }
  ]
}

---

Now, analyze the following SoF document and provide the structured JSON output according to these rules.
"""

# --------------------------- UTILITIES ---------------------------------

def allowed_file(filename: str) -> bool:
    """Checks if the uploaded file has an allowed extension."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(filepath: Path) -> str:
    """Extracts all text content from a PDF file using PyMuPDF."""
    text = ""
    try:
        with fitz.open(filepath) as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        print(f"Error extracting text with PyMuPDF: {e}")
        return ""
    return text

def extract_sof_data_from_text(document_text: str) -> Dict[str, Any]:
    """Sends extracted text to the Gemini API for processing."""
    print("Processing extracted text with the AI model.")
    try:
        model = genai.GenerativeModel(
            LLM_MODEL,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        response = model.generate_content([SOF_EXTRACTION_PROMPT, document_text])
        return json.loads(response.text)
    except Exception as e:
        print(f"Error during AI data extraction from text: {e}")
        return {"error": f"Failed to process text with AI model: {e}"}

def extract_sof_data_from_file(filepath: Path) -> Dict[str, Any]:
    """Uploads a document file (PDF, DOCX) to the Gemini API."""
    print(f"Uploading and processing file: {filepath.name}")
    uploaded_file = None
    try:
        uploaded_file = genai.upload_file(path=filepath)
        model = genai.GenerativeModel(
            LLM_MODEL,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        response = model.generate_content([SOF_EXTRACTION_PROMPT, uploaded_file])
        return json.loads(response.text)
    except Exception as e:
        print(f"Error during AI data extraction from file: {e}")
        return {"error": f"Failed to extract data from file with AI model: {e}"}
    finally:
        if uploaded_file:
            print(f"Deleting uploaded file: {uploaded_file.name}")
            genai.delete_file(uploaded_file.name)


# ------------------------------ FLASK ROUTES ---------------------------------

@app.get("/")
def index() -> str:
    """Renders the main page with the file upload form."""
    return render_template("index.html")

@app.post("/")
def upload_and_process_sof() -> str:
    """Processes the uploaded SoF document and displays analytical results."""
    if 'sof_document' not in request.files:
        return redirect(request.url)

    file = request.files['sof_document']
    render_ctx = {"filename": file.filename}

    if file.filename == '':
        render_ctx["error"] = "No file selected. Please choose a PDF or Word document."
        return render_template("index.html", **render_ctx)

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = UPLOADS_DIR / filename
        file.save(filepath)

        extracted_data = {}
        file_extension = filename.rsplit('.', 1)[1].lower()

        if file_extension == 'docx':
            print("Processing as a DOCX document (using file upload).")
            extracted_data = extract_sof_data_from_file(filepath)
        elif file_extension == 'pdf':
            pdf_type = request.form.get('pdf_type', 'scanned')
            if pdf_type == 'scanned':
                print("Processing as a SCANNED PDF (using file upload).")
                extracted_data = extract_sof_data_from_file(filepath)
            else:
                print("Processing as a TEXT-BASED PDF (extracting text first).")
                document_text = extract_text_from_pdf(filepath)
                if not document_text.strip():
                    extracted_data = {"error": "Could not extract text. The PDF might be image-based. Try the 'Scanned' option."}
                else:
                    extracted_data = extract_sof_data_from_text(document_text)

        # --- NEW: Calculate stats for the results page ---
        if "error" in extracted_data:
            render_ctx["error"] = extracted_data["error"]
        else:
            resolved_events = extracted_data.get("events", [])
            unresolved_events = extracted_data.get("unresolved_events", [])

            resolved_count = len(resolved_events)
            unresolved_count = len(unresolved_events)
            total_items = resolved_count + unresolved_count
            
            success_rate = 0
            if total_items > 0:
                success_rate = math.floor((resolved_count / total_items) * 100)

            # Store main data in session for download links
            session['sof_data'] = resolved_events
            
            # Add all data and stats to the render context
            render_ctx['events'] = resolved_events
            render_ctx['unresolved_events'] = unresolved_events
            render_ctx['resolved_count'] = resolved_count
            render_ctx['unresolved_count'] = unresolved_count
            render_ctx['total_items'] = total_items
            render_ctx['success_rate'] = success_rate

        return render_template("result.html", **render_ctx)
    else:
        render_ctx["error"] = "Invalid file type. Please upload a PDF (.pdf) or Word (.docx) file."
        return render_template("index.html", **render_ctx)

# Download route remains unchanged
@app.get("/download/<filetype>")
def download_file(filetype: str):
    events = session.get('sof_data', [])
    if not events:
        return redirect(url_for('index'))

    if filetype == 'json':
        return Response(
            json.dumps({"events": events}, indent=2),
            mimetype="application/json",
            headers={"Content-Disposition": "attachment;filename=sof_events.json"}
        )
    elif filetype == 'csv':
        output = io.StringIO()
        if events:
            writer = csv.DictWriter(output, fieldnames=events[0].keys())
            writer.writeheader()
            writer.writerows(events)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=sof_events.csv"}
        )
    return redirect(url_for('index'))

# ------------------------------ MAIN -----------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8081, debug=True)
