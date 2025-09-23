import os
from PyPDF2 import PdfReader
from docx import Document
from PIL import Image
import pytesseract


def extract_text(file_path: str) -> str:
    """
    Extract plain text from PDF, DOCX, TXT, or image files.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
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

if __name__ == "__main__":
    import sys, json
    if len(sys.argv) < 2:
        print("Usage: python backend/parser.py <resume_file>")
    else:
        file_path = sys.argv[1]
        raw_text = extract_text(file_path)
        from backend.llm import llm_parse_resume
        parsed = llm_parse_resume(raw_text)
        print(json.dumps(parsed, indent=2))
