#!/usr/bin/env python3
"""
Debug script to test parsing directly
"""

import sys
import os
sys.path.append('.')

from backend.parser import extract_text, fallback_extract
from backend.llm import llm_parse_resume

def test_direct_parsing():
    resume_path = "./samples/resume.pdf"

    if not os.path.exists(resume_path):
        print(f"Resume file not found: {resume_path}")
        return

    try:
        print("1. Testing text extraction...")
        raw_text = extract_text(resume_path)
        print(f"   Extracted {len(raw_text)} characters")
        print(f"   First 200 chars: {raw_text[:200]}")

        print("\n2. Testing LLM parsing...")
        parsed = llm_parse_resume(raw_text)
        print(f"   Parsed JSON keys: {list(parsed.keys())}")

        print("\n3. Testing fallback extraction...")
        final = fallback_extract(raw_text, parsed)
        print(f"   Final JSON keys: {list(final.keys())}")

        print("\n4. Final result:")
        import json
        print(json.dumps(final, indent=2))

    except Exception as e:
        import traceback
        print(f"Error occurred: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    test_direct_parsing()