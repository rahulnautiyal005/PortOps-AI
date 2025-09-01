# SoF AI Extractor

A web-based application that uses **Google's Gemini AI** to automatically extract port operation events, start times, and end times from "Statement of Facts" (SoF) documents. The system accepts PDF and Word files, processes them in a template-agnostic way, and provides the structured data for download as **JSON** or **CSV**.

---

## 📸 Screenshots
Here are some sample screenshots of the application:

### 1. Front Page UI  
![Screenshot 1](static/Screenshot%202025-08-20%20225054.png)  

### 2. Uploading a Document (PDF or DOCX)  
![Screenshot 2](static/Screenshot%202025-08-20%20225114.png)  

### 3. Sample PDF Used for Extraction  
![Screenshot 6](static/Screenshot%202025-08-20%20225232.png)  

### 4. Extraction Results with Download Options (CSV or JSON)  
![Screenshot 3](static/Screenshot%202025-08-20%20225138.png)  

### 5. Extracted Data in CSV Format  
![Screenshot 4](static/Screenshot%202025-08-20%20225202.png)  

### 6. Extracted Data in JSON Format  
![Screenshot 5](static/Screenshot%202025-08-20%20225220.png)  
 


---

## ✨ Features
- **AI-Powered Extraction**: Leverages the Google Gemini Flash model for intelligent and accurate data extraction.  
- **Multi-Format Support**: Accepts both PDF (`.pdf`) and Word (`.docx`) documents.  
- **Template-Agnostic**: Works with various SoF layouts and formats without pre-configuration.  
- **Structured Output**: Converts unstructured text into a clean, structured list of events.  
- **Data Download**: Allows users to download extracted data in both JSON and CSV formats.  
- **Modern UI**: Clean, responsive, and user-friendly interface with a drag-and-drop file upload zone.  

---

## 🛠️ Tech Stack
- **Backend**: Python 3  
- **Web Framework**: Flask  
- **AI Model**: Google Gemini 1.5 Flash  
- **Document Processing**:  
  - `PyPDF2` for PDF text extraction  
  - `python-docx` for Word document text extraction  
- **Frontend**: HTML5, Bootstrap 5, Custom CSS & JavaScript  

---

## 🚀 Setup and Installation

### 1. Prerequisites
- Python **3.8 or newer**  
- A **Google Gemini API Key** (available from Google AI Studio)

### 2. Clone the Repository
```bash
git clone https://github.com/your-username/sof-ai-extractor.git
cd sof-ai-extractor
```

### 3. Install Dependencies
```bash
# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
```

### 4. Install the required packages
```bash
pip install Flask google-generativeai python-dotenv PyPDF2 python-docx
```

### 5. set up Environment variables
```bash
GEMINI_API_KEY="YOUR_API_KEY_HERE"
```

## How to Run
```bash
python app.py
```
