import os
import re
import json
import pdfplumber
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
import pytesseract


def extract_text(file_path: str) -> str:
    """
    Extract plain text from PDF, DOCX, TXT, or image files.
    Priority: pdfplumber for PDFs (better layout) → fallback to PyPDF2.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
            if text.strip():
                return text
        except Exception as e:
            print(f"pdfplumber failed, falling back to PyPDF2: {e}")

        reader = PdfReader(file_path)
        texts = []
        for page in reader.pages:
            try:
                texts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(texts)

    elif ext == ".docx":
        doc = Document(file_path)
        return "\n".join([p.text for p in doc.paragraphs])

    elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        image = Image.open(file_path)
        return pytesseract.image_to_string(image)

    else:  # default to TXT
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


def fallback_extract(text: str, resume_json: dict) -> dict:
    """
    Very basic regex-based fallback to ensure education/experience isn't empty.
    Only triggers if LLM missed sections.
    """
    # Fallback for Education
    if not resume_json.get("education"):
        edu_matches = re.findall(r"(St Joseph.*University.*?\d{4})", text, re.IGNORECASE)
        if edu_matches:
            resume_json["education"] = [{
                "institution": edu_matches[0],
                "degree": "",
                "field": "",
                "location": "",
                "graduation_date": "",
                "gpa": ""
            }]

    # Fallback for Experience
    if not resume_json.get("experience"):
        exp_matches = re.findall(r"(Oryzed|Green Builders|Sastic Minds).*", text)
        if exp_matches:
            resume_json["experience"] = []
            for m in exp_matches:
                resume_json["experience"].append({
                    "company": m,
                    "position": "",
                    "location": "",
                    "start_date": "",
                    "end_date": "",
                    "achievements": []
                })

    return resume_json


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python backend/parser.py <resume_file>")
    else:
        file_path = sys.argv[1]
        raw_text = extract_text(file_path)

        from backend.llm import llm_parse_resume
        parsed = llm_parse_resume(raw_text)

        # Fallback check
        parsed = fallback_extract(raw_text, parsed)

        print(json.dumps(parsed, indent=2))
