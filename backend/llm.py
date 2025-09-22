import os
from typing import Dict, Any, List

import google.generativeai as genai


PROMPT_TEMPLATE = (
    """
You are a professional resume optimization system.
Input: Resume JSON + Job Description.

CRITICAL RULES - DATA PRESERVATION:
- NEVER add companies, positions, projects, or skills not in the original resume
- NEVER invent dates, locations, or metrics not in the original data
- ONLY rewrite/optimize existing content to better match the job description
- Do NOT create new experience bullets - only improve existing ones
- Do NOT add technologies, skills, or achievements not mentioned in original resume

Your job is to:
1. Rewrite EXISTING summary to better target the role (if summary exists)
2. Optimize EXISTING experience bullets for ATS and readability (≤1.5 lines each)
3. Reorder EXISTING skills by relevance to job description
4. Select top 2-3 EXISTING projects most relevant to the role

Constraints:
- Keep all original quantified results (%, $, numbers) exactly as they are
- Preserve all company names, dates, and locations exactly
- Maximum 3-4 bullets per experience entry (for one-page format)
- Return only data that was in the original resume

Output JSON:
{
  "rewritten_summary": "...",
  "rewritten_experience": [...],
  "ranked_skills": {...},
  "ranked_projects": [...]
}
"""
).strip()

COVER_LETTER_TEMPLATE = (
    """
You are a professional cover letter writer.
Input: Resume JSON + Job Description + Company Name + Position Title.

Rules:
- Write a professional business letter format cover letter
- 300-350 words maximum
- Address specific requirements from the job description
- Highlight relevant experience and achievements from the resume
- Use quantified metrics where available
- Professional, confident tone
- Include proper business letter structure

Output format: Plain text business letter (no JSON)
"""
).strip()

INTERVIEW_QUESTIONS_TEMPLATE = (
    """
You are an interview preparation expert.
Input: Resume JSON + Job Description + Company Name + Position Title.

Rules:
- Generate 8-10 interview questions total:
  - 3-4 technical questions specific to the role
  - 3-4 behavioral questions using STAR method
  - 1-2 company/role-specific questions
- Questions should be realistic and commonly asked
- Focus on skills and experience mentioned in the resume and job description
- Provide a mix of difficulty levels

Output format: Numbered list of questions (no JSON)
"""
).strip()


def _get_model() -> Any:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        # Fallback to a hardcoded key for testing
        api_key = "AIzaSyBApwUQwyC8fdB59houV5Ofx5yNQSgUX_M"
    genai.configure(api_key=api_key)
    return genai.GenerativeModel("gemini-1.5-flash")


def rewrite_resume(resume_json: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    model = _get_model()
    system_and_input = (
        f"{PROMPT_TEMPLATE}\n\nResume JSON:\n{resume_json}\n\nJob Description:\n{job_description}\n"
    )
    response = model.generate_content(system_and_input)
    text = response.text or "{}"
    # Be lenient: model must return JSON; fallback to empty structure on failure
    import json

    try:
        payload = json.loads(text)
    except Exception:
        payload = {
            "rewritten_summary": resume_json.get("summary", ""),
            "rewritten_experience": [
                {"company": e.get("company", ""), "bullets": e.get("achievements", [])}
                for e in resume_json.get("experience", [])
            ],
            "ranked_skills": resume_json.get("skills", {}),
            "ranked_projects": [p.get("title", "") for p in resume_json.get("projects", [])][:3],
        }
    return payload


def generate_cover_letter(resume_json: Dict[str, Any], job_description: str, company_name: str = "", position_title: str = "") -> str:
    model = _get_model()

    # Extract company and position from job description if not provided
    if not company_name:
        company_name = "the hiring company"
    if not position_title:
        position_title = "the position"

    prompt = (
        f"{COVER_LETTER_TEMPLATE}\n\n"
        f"Resume JSON:\n{resume_json}\n\n"
        f"Job Description:\n{job_description}\n\n"
        f"Company Name: {company_name}\n"
        f"Position Title: {position_title}\n\n"
        f"Generate a professional cover letter:"
    )

    try:
        response = model.generate_content(prompt)
        return response.text or "Unable to generate cover letter at this time."
    except Exception:
        return "Unable to generate cover letter at this time."


def generate_interview_questions(resume_json: Dict[str, Any], job_description: str, company_name: str = "", position_title: str = "") -> str:
    model = _get_model()

    # Extract company and position from job description if not provided
    if not company_name:
        company_name = "the hiring company"
    if not position_title:
        position_title = "the position"

    prompt = (
        f"{INTERVIEW_QUESTIONS_TEMPLATE}\n\n"
        f"Resume JSON:\n{resume_json}\n\n"
        f"Job Description:\n{job_description}\n\n"
        f"Company Name: {company_name}\n"
        f"Position Title: {position_title}\n\n"
        f"Generate interview questions:"
    )

    try:
        response = model.generate_content(prompt)
        return response.text or "Unable to generate interview questions at this time."
    except Exception:
        return "Unable to generate interview questions at this time."


__all__ = ["rewrite_resume", "generate_cover_letter", "generate_interview_questions"]


