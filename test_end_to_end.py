#!/usr/bin/env python3
"""
End-to-end test harness for ResBot pipeline.
Tests the complete flow: parse -> rewrite -> ats -> render

Usage: python test_end_to_end.py
"""

import os
import sys
import json
import requests
import time
from pathlib import Path

# Configuration
API_BASE_URL = "http://localhost:8000"
SAMPLE_RESUME_PATH = "./samples/Resume.pdf"
OUTPUT_DIR = "./test_outputs"

# Sample job description for testing
SAMPLE_JOB_DESCRIPTION = """
Senior Python Developer

We are seeking a Senior Python Developer to join our dynamic team. The ideal candidate will have:

Requirements:
- 3+ years of Python development experience
- Experience with FastAPI, Flask, or Django
- Knowledge of SQL databases (PostgreSQL, MySQL)
- Experience with cloud platforms (AWS, Azure, GCP)
- Familiarity with Docker and containerization
- Understanding of RESTful API development
- Experience with Git version control
- Knowledge of data structures and algorithms

Nice to have:
- Machine learning experience with scikit-learn, pandas, numpy
- Frontend development with React or Vue.js
- DevOps experience with CI/CD pipelines
- Experience with microservices architecture

Responsibilities:
- Develop and maintain Python-based web applications
- Design and implement RESTful APIs
- Collaborate with cross-functional teams
- Write clean, maintainable code
- Participate in code reviews
- Troubleshoot and debug applications
"""


def ensure_output_dir():
    """Create output directory if it doesn't exist."""
    Path(OUTPUT_DIR).mkdir(exist_ok=True)


def check_api_health():
    """Check if API is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/")
        if response.status_code == 200:
            print("✅ API is running")
            return True
        else:
            print(f"❌ API health check failed: {response.status_code}")
            return False
    except requests.ConnectionError:
        print("❌ Cannot connect to API. Is the server running?")
        print("   Start the server with: uvicorn backend.api:app --reload")
        return False


def test_parse_resume():
    """Test /parse endpoint."""
    print("\n📄 Testing resume parsing...")

    if not os.path.exists(SAMPLE_RESUME_PATH):
        print(f"❌ Sample resume not found at {SAMPLE_RESUME_PATH}")
        return None

    try:
        print(f"   Opening file: {SAMPLE_RESUME_PATH}")
        with open(SAMPLE_RESUME_PATH, "rb") as f:
            files = {"file": ("resume.pdf", f, "application/pdf")}
            print(f"   Making request to {API_BASE_URL}/parse")
            response = requests.post(f"{API_BASE_URL}/parse", files=files, timeout=60)
            print(f"   Response status: {response.status_code}")

        if response.status_code == 200:
            parsed_data = response.json()
            if "error" in parsed_data:
                print(f"❌ Parse error: {parsed_data['error']}")
                return None

            print("✅ Resume parsed successfully")
            print(f"   Contact: {parsed_data.get('contact_info', {}).get('full_name', 'N/A')}")
            print(f"   Education entries: {len(parsed_data.get('education', []))}")
            print(f"   Experience entries: {len(parsed_data.get('experience', []))}")
            print(f"   Projects entries: {len(parsed_data.get('projects', []))}")
            print(f"   Skills categories: {len(parsed_data.get('skills', {}))}")

            # Save parsed data
            with open(f"{OUTPUT_DIR}/parsed_resume.json", "w") as f:
                json.dump(parsed_data, f, indent=2)

            return parsed_data
        else:
            print(f"❌ Parse failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Parse error: {e}")
        return None


def test_rewrite_resume(parsed_resume):
    """Test /rewrite endpoint."""
    print("\n🔄 Testing resume rewriting...")

    if not parsed_resume:
        print("❌ No parsed resume to rewrite")
        return None

    try:
        payload = {
            "resume_json": parsed_resume,
            "job_description": SAMPLE_JOB_DESCRIPTION
        }

        response = requests.post(f"{API_BASE_URL}/rewrite", json=payload, timeout=60)

        if response.status_code == 200:
            rewritten_data = response.json()
            if "error" in rewritten_data:
                print(f"❌ Rewrite error: {rewritten_data['error']}")
                return None

            print("✅ Resume rewritten successfully")
            print(f"   Summary updated: {'Yes' if rewritten_data.get('summary') else 'No'}")
            print(f"   Skills categories: {len(rewritten_data.get('skills', {}))}")

            # Save rewritten data
            with open(f"{OUTPUT_DIR}/rewritten_resume.json", "w") as f:
                json.dump(rewritten_data, f, indent=2)

            return rewritten_data
        else:
            print(f"❌ Rewrite failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ Rewrite error: {e}")
        return None


def test_ats_scoring(resume_data):
    """Test /ats endpoint."""
    print("\n📊 Testing ATS scoring...")

    if not resume_data:
        print("❌ No resume data for ATS scoring")
        return None

    try:
        payload = {
            "resume_json": resume_data,
            "job_description": SAMPLE_JOB_DESCRIPTION
        }

        response = requests.post(f"{API_BASE_URL}/ats", json=payload, timeout=60)

        if response.status_code == 200:
            ats_data = response.json()
            if "error" in ats_data:
                print(f"❌ ATS error: {ats_data['error']}")
                return None

            print("✅ ATS scoring completed")
            print(f"   Overall Score: {ats_data.get('ats_score', 'N/A')}/100")

            breakdown = ats_data.get('score_breakdown', {})
            print(f"   Skills: {breakdown.get('skills', 'N/A')}/100")
            print(f"   Keywords: {breakdown.get('keywords', 'N/A')}/100")
            print(f"   Title: {breakdown.get('title', 'N/A')}/100")
            print(f"   Experience: {breakdown.get('experience', 'N/A')}/100")

            keyword_matches = ats_data.get('keyword_matches', {})
            print(f"   Technical matches: {len(keyword_matches.get('technical', []))}")
            print(f"   Business matches: {len(keyword_matches.get('business', []))}")

            recommendations = ats_data.get('recommendations', [])
            print(f"   Recommendations: {len(recommendations)}")

            # Save ATS data
            with open(f"{OUTPUT_DIR}/ats_results.json", "w") as f:
                json.dump(ats_data, f, indent=2)

            return ats_data
        else:
            print(f"❌ ATS scoring failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return None

    except Exception as e:
        print(f"❌ ATS scoring error: {e}")
        return None


def test_render_resume(resume_data):
    """Test /render endpoint."""
    print("\n📄 Testing resume rendering...")

    if not resume_data:
        print("❌ No resume data for rendering")
        return False

    try:
        response = requests.post(f"{API_BASE_URL}/render", json=resume_data, timeout=60)

        if response.status_code == 200:
            # Check if response contains error JSON
            try:
                error_data = response.json()
                if "error" in error_data:
                    print(f"❌ Render error: {error_data['error']}")
                    return False
            except:
                # Response is binary DOCX data, which is expected
                pass

            # Save DOCX file
            output_path = f"{OUTPUT_DIR}/rendered_resume.docx"
            with open(output_path, "wb") as f:
                f.write(response.content)

            print("✅ Resume rendered successfully")
            print(f"   Output saved to: {output_path}")
            print(f"   File size: {len(response.content)} bytes")

            return True
        else:
            print(f"❌ Render failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Render error: {e}")
        return False


def test_cover_letter(resume_data):
    """Test /cover-letter endpoint."""
    print("\n📝 Testing cover letter generation...")

    if not resume_data:
        print("❌ No resume data for cover letter")
        return False

    try:
        payload = {
            "resume_json": resume_data,
            "job_description": SAMPLE_JOB_DESCRIPTION,
            "company_name": "TechCorp",
            "position_title": "Senior Python Developer"
        }

        response = requests.post(f"{API_BASE_URL}/cover-letter", json=payload, timeout=60)

        if response.status_code == 200:
            # Check if response contains error JSON
            try:
                error_data = response.json()
                if "error" in error_data:
                    print(f"❌ Cover letter error: {error_data['error']}")
                    return False
            except:
                # Response is binary text data, which is expected
                pass

            # Save cover letter
            output_path = f"{OUTPUT_DIR}/cover_letter.txt"
            with open(output_path, "wb") as f:
                f.write(response.content)

            print("✅ Cover letter generated successfully")
            print(f"   Output saved to: {output_path}")
            print(f"   Content length: {len(response.content)} bytes")

            return True
        else:
            print(f"❌ Cover letter failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Cover letter error: {e}")
        return False


def test_interview_questions(resume_data):
    """Test /interview-questions endpoint."""
    print("\n❓ Testing interview questions generation...")

    if not resume_data:
        print("❌ No resume data for interview questions")
        return False

    try:
        payload = {
            "resume_json": resume_data,
            "job_description": SAMPLE_JOB_DESCRIPTION,
            "company_name": "TechCorp",
            "position_title": "Senior Python Developer"
        }

        response = requests.post(f"{API_BASE_URL}/interview-questions", json=payload, timeout=60)

        if response.status_code == 200:
            # Check if response contains error JSON
            try:
                error_data = response.json()
                if "error" in error_data:
                    print(f"❌ Interview questions error: {error_data['error']}")
                    return False
            except:
                # Response is binary text data, which is expected
                pass

            # Save interview questions
            output_path = f"{OUTPUT_DIR}/interview_questions.txt"
            with open(output_path, "wb") as f:
                f.write(response.content)

            print("✅ Interview questions generated successfully")
            print(f"   Output saved to: {output_path}")
            print(f"   Content length: {len(response.content)} bytes")

            return True
        else:
            print(f"❌ Interview questions failed with status {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Interview questions error: {e}")
        return False


def main():
    """Run the complete end-to-end test suite."""
    print("🧪 ResBot End-to-End Test Suite")
    print("=" * 50)

    # Setup
    ensure_output_dir()

    # Check API health
    if not check_api_health():
        sys.exit(1)

    # Test pipeline
    test_results = {
        "parse": False,
        "rewrite": False,
        "ats": False,
        "render": False,
        "cover_letter": False,
        "interview_questions": False
    }

    # 1. Parse resume
    parsed_resume = test_parse_resume()
    test_results["parse"] = parsed_resume is not None

    # 2. Rewrite resume (use parsed data)
    rewritten_resume = test_rewrite_resume(parsed_resume)
    test_results["rewrite"] = rewritten_resume is not None

    # Use rewritten data for subsequent tests (fallback to parsed if rewrite failed)
    final_resume_data = rewritten_resume or parsed_resume

    # 3. ATS scoring
    ats_results = test_ats_scoring(final_resume_data)
    test_results["ats"] = ats_results is not None

    # 4. Render resume
    test_results["render"] = test_render_resume(final_resume_data)

    # 5. Generate cover letter
    test_results["cover_letter"] = test_cover_letter(final_resume_data)

    # 6. Generate interview questions
    test_results["interview_questions"] = test_interview_questions(final_resume_data)

    # Summary
    print("\n" + "=" * 50)
    print("📋 Test Results Summary:")
    print("=" * 50)

    total_tests = len(test_results)
    passed_tests = sum(test_results.values())

    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {test_name.replace('_', ' ').title()}: {status}")

    print(f"\n🎯 Overall: {passed_tests}/{total_tests} tests passed")

    if passed_tests == total_tests:
        print("🎉 All tests passed! The ResBot pipeline is working correctly.")
        return 0
    else:
        print("⚠️  Some tests failed. Check the error messages above.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)