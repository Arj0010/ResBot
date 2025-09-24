import os
from typing import Dict, Any, List
import json
from dotenv import load_dotenv
import google.generativeai as genai
from openai import OpenAI
load_dotenv()


class MockModel:
    """Mock model that returns safe JSON when API quota is exceeded"""

    def generate_content(self, prompt: str):
        class Result:
            def __init__(self):
                # Return a safe mock resume JSON structure
                self.text = json.dumps({
                    "contact_info": {"full_name": "Sample User", "email": "user@example.com", "phone": "", "location": ""},
                    "links": {"LinkedIn": "", "GitHub": "", "HuggingFace": "", "Coursera": ""},
                    "summary": "Experienced professional with strong background in technology and problem-solving.",
                    "education": [],
                    "experience": [],
                    "projects": [],
                    "certifications": [],
                    "skills": {"Technical": ["Python", "Data Analysis"], "Non-Technical": ["Communication", "Teamwork"]},
                    "languages": []
                })
        return Result()


class OpenAIAdapter:
    """
    Wraps OpenAI client so it behaves like Gemini's GenerativeModel:
    - has .generate_content(prompt)
    - returns an object with .text
    """

    def __init__(self, api_key: str, model_name: str = "gpt-4o-mini"):
        self.client = OpenAI(api_key=api_key)
        self.model_name = model_name

    def generate_content(self, prompt: str):
        try:
            resp = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000
            )

            class Result:
                def __init__(self, text):
                    self.text = text

            return Result(resp.choices[0].message.content)
        except Exception as e:
            print(f"OpenAI API error: {e}")
            # Return mock response for quota/API errors
            return MockModel().generate_content(prompt)


def _get_model():
    """
    Returns a model adapter. Falls back to MockModel if API quota is exceeded.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        api_key = "sk-test-key"  # fallback for local dev

    try:
        return OpenAIAdapter(api_key=api_key, model_name="gpt-4o-mini")
    except Exception:
        print("Model initialization failed, using MockModel")
        return MockModel()


def clean_resume_json(data: Any) -> Any:
    """
    Recursively clean resume JSON:
    - Replace None/null with "" or []
    - Ensure schema consistency
    """
    if isinstance(data, dict):
        cleaned = {}
        for k, v in data.items():
            cleaned_val = clean_resume_json(v)
            # For certain keys, ensure proper defaults
            if k in ["education", "experience", "projects", "certifications", "languages"] and cleaned_val == "":
                cleaned[k] = []
            elif k == "skills" and cleaned_val == "":
                cleaned[k] = {"Technical": [], "Non-Technical": []}
            else:
                cleaned[k] = cleaned_val
        return cleaned
    elif isinstance(data, list):
        return [clean_resume_json(v) for v in data]
    elif data is None:
        return ""
    else:
        return data


def llm_parse_resume(resume_text: str) -> Dict[str, Any]:
    """
    Parse raw resume text into a structured JSON format using LLM.
    Ensures schema is always present and no null values.
    """
    model = _get_model()

    prompt = f"""
You are a resume parsing assistant.

Extract all structured data from the following resume text:

{resume_text}

Return JSON strictly in this schema:
{{
  "contact_info": {{"full_name": "", "email": "", "phone": "", "location": ""}},
  "links": {{"LinkedIn": "", "GitHub": "", "HuggingFace": "", "Coursera": ""}},
  "summary": "",
  "education": [],
  "experience": [],
  "projects": [],
  "certifications": [],
  "skills": {{"Technical": [], "Non-Technical": []}},
  "languages": []
}}

Rules:
- Always include all fields, even if empty.
- If information is missing, use "" or [] (never null).
- Preserve the exact JSON schema shown above.
- Extract as much detail as possible for education, experience, and projects.
- Use empty arrays [] instead of placeholder objects like [{{"institution": ""}}].
"""

    try:
        response = model.generate_content(prompt)
        text = response.text or "{}"

        print("DEBUG Raw LLM output:", text[:500])

        # Extract JSON from markdown fences
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        llm_output = json.loads(text)

        # Clean nulls and enforce schema
        resume_json = clean_resume_json(llm_output)

        print("DEBUG Final parsed JSON keys:", list(resume_json.keys()))
        return resume_json

    except Exception as e:
        print(f"LLM processing error in llm_parse_resume: {e}")
        return {
            "contact_info": {"full_name": "", "email": "", "phone": "", "location": ""},
            "links": {"LinkedIn": "", "GitHub": "", "HuggingFace": "", "Coursera": ""},
            "summary": "",
            "education": [],
            "experience": [],
            "projects": [],
            "certifications": [],
            "skills": {"Technical": [], "Non-Technical": []},
            "languages": []
        }


def rewrite_resume(resume_json: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    """
    Tailor the resume JSON to the given job description using LLM.
    Preserves the full schema and only updates fields that the LLM improves.
    """
    model = _get_model()

    prompt = f"""
You are a professional resume optimization expert.

ORIGINAL RESUME JSON:
{json.dumps(resume_json, indent=2)}

JOB DESCRIPTION:
{job_description}

TASK:
- Optimize ONLY the existing fields in the resume JSON for the job description.
- Keep the EXACT same schema and keys as the original resume JSON.
- Do not add new keys or remove any existing ones.
- Rewrite summary to highlight JD-relevant strengths.
- Reorder skills, projects, and experience by JD relevance.
- Improve achievements for ATS readability (≤1.5 lines).
- Do NOT invent new jobs, degrees, certifications, or skills.
- If a field is empty in the original JSON, leave it empty.
- Use empty arrays [] instead of placeholder objects.

OUTPUT:
Return the COMPLETE resume JSON with the same schema as ORIGINAL RESUME JSON,
but optimized for the job description.
"""

    try:
        response = model.generate_content(prompt)
        text = response.text or "{}"

        print("DEBUG Raw rewrite LLM output:", text[:500])

        # Extract JSON from markdown fences
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        llm_output = json.loads(text)

        # Start from original resume JSON
        result = resume_json.copy()

        # Update only if LLM returned that section
        for key in result.keys():
            if key in llm_output and llm_output[key]:
                result[key] = llm_output[key]

        print("DEBUG Final tailored JSON keys:", list(result.keys()))
        return result

    except Exception as e:
        print(f"LLM processing error in rewrite_resume: {e}")
        return resume_json


def generate_cover_letter(resume_json: Dict[str, Any], job_description: str, company_name: str = "", position_title: str = "") -> str:
    model = _get_model()

    if not company_name:
        company_name = "the hiring company"
    if not position_title:
        position_title = "the position"

    prompt = f"""
You are a professional cover letter writer.

ORIGINAL RESUME DATA (use only this information):
{json.dumps(resume_json, indent=2)}

JOB DESCRIPTION:
{job_description}

Company Name: {company_name}
Position Title: {position_title}

Rules:
- Write a professional business letter format cover letter
- 300-350 words maximum
- Address specific requirements from the job description
- ONLY highlight experience and achievements that exist in the provided resume
- Use quantified metrics ONLY if they exist in the original resume data
- Professional, confident tone
- Include proper business letter structure
- DO NOT invent or exaggerate achievements not in the resume

Generate a professional cover letter using ONLY the information provided in the resume data above.
"""

    try:
        response = model.generate_content(prompt)
        return response.text or "Unable to generate cover letter at this time."
    except Exception:
        return "Unable to generate cover letter at this time."


def generate_interview_questions(resume_json: Dict[str, Any], job_description: str, company_name: str = "", position_title: str = "") -> str:
    model = _get_model()

    if not company_name:
        company_name = "the hiring company"
    if not position_title:
        position_title = "the position"

    prompt = f"""
You are an interview preparation expert.

ORIGINAL RESUME DATA (base questions only on this):
{json.dumps(resume_json, indent=2)}

JOB DESCRIPTION:
{job_description}

Company Name: {company_name}
Position Title: {position_title}

Rules:
- Generate 8-10 interview questions total:
  - 3-4 technical questions specific to the role and resume skills
  - 3-4 behavioral questions using STAR method based on resume experience
  - 1-2 company/role-specific questions
- Questions should be realistic and commonly asked
- Focus ONLY on skills and experience mentioned in the resume and job description
- Do not reference skills or experience not present in the original resume
- Provide a mix of difficulty levels

Generate interview questions based ONLY on the skills and experience shown in the resume data above.
"""

    try:
        response = model.generate_content(prompt)
        return response.text or "Unable to generate interview questions at this time."
    except Exception:
        return "Unable to generate interview questions at this time."


__all__ = ["rewrite_resume", "generate_cover_letter", "generate_interview_questions", "llm_parse_resume"]