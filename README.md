# AI-Powered Resume Builder (Harvard Default Template)

## Objective
An AI-powered resume builder that:
1. Parses resumes (PDF/DOCX/TXT/Image).
2. Converts them into structured JSON (source of truth).
3. Uses LLMs to rewrite only summary, bullets, and skill/project ordering.
4. Renders Harvard-style resume as the default template.
5. Provides ATS scoring and optional cover letter/interview questions.
6. Supports multiple templates in the future via JSON configs.

---

## Core Logic

### 1. Parser (Immutable Resume JSON)
- Input: Resume file (PDF, DOCX, TXT, or image via OCR).
- Output JSON schema:

```json
{
  "contact_info": {
    "full_name": "string",
    "email": "string",
    "phone": "string",
    "location": "string"
  },
  "links": {
    "LinkedIn": "url",
    "GitHub": "url",
    "HuggingFace": "url",
    "Coursera": "url"
  },
  "summary": "string",
  "education": [
    {
      "institution": "string",
      "degree": "string",
      "field": "string",
      "location": "string",
      "graduation_date": "string",
      "gpa": "string"
    }
  ],
  "experience": [
    {
      "company": "string",
      "position": "string",
      "location": "string",
      "start_date": "string",
      "end_date": "string",
      "achievements": ["string"]
    }
  ],
  "projects": [
    {
      "title": "string",
      "description": "string",
      "technologies": ["string"],
      "bullets": ["string"]
    }
  ],
  "certifications": ["string"],
  "skills": {
    "Programming & Tools": ["string"],
    "ML & AI": ["string"],
    "Analytics": ["string"]
  },
  "languages": ["string"]
}
```

- Rules:
  - Must never drop metrics, numbers, dates, timelines, links, or certificates.
  - Links stored as dict and rendered later as **text-labeled hyperlinks** (e.g., “LinkedIn” not raw URL).
  - All sections must exist in JSON, even if empty.

---

### 2. LLM Rewrite Layer
- Input: `resume_json + job_description`.
- Tasks:
  - Rewrite **summary** → ≤3 lines, keep quantified metrics.
  - Rewrite **bullets** → STAR style, concise, keep metrics/numbers.
  - Rank **skills** by JD relevance.
  - Rank **projects** by JD relevance, max 3.
- Output partial JSON:

```json
{
  "rewritten_summary": "string",
  "rewritten_experience": [
    {"company": "string", "bullets": ["string"]}
  ],
  "ranked_skills": {...},
  "ranked_projects": ["string", "string", "string"]
}
```

- Merge with parser JSON → parser JSON always wins for structure (no data loss).

---

### 3. Template Renderer
- Default = Harvard Style (based on provided sample).
- Template defined as JSON config:

```json
{
  "font": "Calibri",
  "font_size": 10,
  "margins": {"top": 0.6, "bottom": 0.6, "left": 0.6, "right": 0.6},
  "section_order": [
    "contact_info",
    "summary",
    "education",
    "experience",
    "projects",
    "certifications",
    "skills",
    "languages"
  ],
  "section_titles": {
    "summary": "CAREER OBJECTIVE",
    "certifications": "CERTIFICATES"
  }
}
```

- Formatting Rules:
  - Calibri 10, bold headers, no underlines.
  - Links as **text-labeled hyperlinks** (LinkedIn, GitHub, HuggingFace, Coursera).
  - Experience: Company → Role → Dates → Bullets.
  - Education: clean timeline (no placeholders).
  - Skills: grouped by category, comma-separated.
  - Projects: max 3, sorted by JD relevance.
  - Languages: always included.
  - Enforce 1-page → trim bullets from older roles first.

- Future templates = swap config.

---

### 4. ATS Analyzer
- Weighted scoring:
  - Skills match: 40%
  - JD keyword overlap: 30%
  - Job title similarity: 20%
  - Experience length: 10%
- Output JSON:

```json
{
  "ats_score": 85,
  "keyword_matches": {"technical": ["Python", "SQL"], "business": ["Agile"]},
  "missing_keywords": ["TensorFlow", "Kubernetes"],
  "recommendations": [
    "Add TensorFlow to projects",
    "Mention Kubernetes in achievements"
  ]
}
```

- UI: Show bar + % + recommendations.

---

### 5. Optional Toggles
- **Cover Letter** → plain `.docx`, business letter format, 300–350 words.
- **Interview Questions** → 8–10 Qs (3–4 technical, 3–4 behavioral, 1–2 role/company-specific).
- Toggles OFF by default, user enables ON.

---

## Tech Stack
- Backend: Python, FastAPI
- Frontend: Gradio
- Parsing: PyPDF2, python-docx, pytesseract
- LLM: Google Gemini API
- Data: JSON schema
- Doc Generation: python-docx
- ATS Scoring: Python logic

---

## UI Requirements
- Upload resume (PDF/DOCX/TXT/Image).
- Paste/upload JD.
- Toggles for Cover Letter + Interview Questions.
- Display:
  - Resume Preview (Harvard style, hyperlinks working).
  - ATS Score Bar + Recommendations.
- Download:
  - Resume (docx/pdf).
  - Cover Letter (docx, if generated).
  - Interview Questions (txt/docx, if generated).

---

## Future-Proofing
- Templates defined as JSON configs → easy to add new templates.
- Parser JSON schema fixed.
- Only template config changes for new styles.

---

## LLM Prompt Template
```
You are a professional resume optimization system.
Input: Resume JSON + Job Description.

Rules:
- Do not delete any companies, projects, skills, or links.
- Always preserve all metrics, numbers, timelines, certificates, and languages.
- Rewrite only: summary and experience bullets (STAR format, ≤1.5 lines per bullet).
- Keep all quantified results (%, $, numbers).
- Rank skills and projects by JD relevance (return top 3 projects).
- Return structured JSON only, no free text.

Output JSON:
{
  "rewritten_summary": "...",
  "rewritten_experience": [...],
  "ranked_skills": {...},
  "ranked_projects": [...]
}
```

---

## Quickstart

1. Create a virtual environment and install dependencies:
   - Windows PowerShell:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     pip install -r requirements.txt
     ```

2. Set environment variable for Gemini:
   - Persist for next sessions:
     ```powershell
     setx GOOGLE_API_KEY "AIzaSyBApwUQwyC8fdB59houV5Ofx5yNQSgUX_M"
"
     ```
     For current shell only:
     ```powershell
     $env:GOOGLE_API_KEY = "YOUR_KEY_HERE"
     ```

3. Run backend API:
   ```powershell
   uvicorn backend.api:app --reload
   ```

4. Run frontend UI (in another terminal):
   ```powershell
   python frontend/app.py
   ```

5. Run tests:
   ```powershell
   pytest -q
   ```

Notes:
- UI shows ATS score bar with percent and recommendations.
- Renderer preserves links as text-labeled hyperlinks (LinkedIn, GitHub, HuggingFace, Coursera).
- Harvard template config is in `templates/harvard.json`.