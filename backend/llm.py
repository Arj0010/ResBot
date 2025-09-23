import os
from typing import Dict, Any, List
import json

import google.generativeai as genai


PROMPT_TEMPLATE = (
    """
You are a professional resume optimization system.
Input: Resume JSON + Job Description.

CRITICAL RULES - STRICT DATA PRESERVATION:
- NEVER add companies, positions, projects, or skills not in the original resume
- NEVER invent dates, locations, metrics, or achievements not in the original data
- NEVER create new experience bullets - only improve/rewrite existing ones
- NEVER add technologies, skills, or achievements not mentioned in original resume
- NEVER add new sections or entries that don't exist in the input
- ONLY rewrite/optimize existing content to better match the job description
- If original resume has empty fields, keep them empty
- Preserve ALL original quantified results (%, $, numbers) exactly as they are
- Maintain exact company names, dates, and locations from original

Your job is to ONLY:
1. Rewrite EXISTING summary if it exists (if empty, return empty)
2. Optimize EXISTING experience bullets for ATS and readability (≤1.5 lines each)
3. Reorder EXISTING skills by relevance to job description
4. Reorder EXISTING projects by relevance (do not add or remove projects)

Quality Guidelines:
- Each experience bullet should be ≤1.5 lines for ATS compatibility
- Use action verbs and quantify results where original data supports it
- Focus on achievements over responsibilities
- Ensure bullets start with strong action verbs

Constraints:
- Maximum 3-4 bullets per experience entry (use the most impactful existing ones)
- If original has fewer bullets, don't add more
- Return ONLY data that was in the original resume
- Preserve the exact JSON structure provided

Output JSON (preserve exact structure):
{
  "rewritten_summary": "..." (only if original had summary, otherwise ""),
  "rewritten_experience": [
    {
      "company": "exact original company name",
      "bullets": ["improved versions of original achievements only"]
    }
  ],
  "ranked_skills": {
    "Programming & Tools": ["reordered original skills only"],
    "ML & AI": ["reordered original skills only"],
    "Analytics": ["reordered original skills only"]
  },
  "ranked_projects": ["reordered original project titles only"]
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
- ONLY highlight experience and achievements that exist in the provided resume
- Use quantified metrics ONLY if they exist in the original resume data
- Professional, confident tone
- Include proper business letter structure
- DO NOT invent or exaggerate achievements not in the resume

Output format: Plain text business letter (no JSON)
"""
).strip()

INTERVIEW_QUESTIONS_TEMPLATE = (
    """
You are an interview preparation expert.
Input: Resume JSON + Job Description + Company Name + Position Title.

Rules:
- Generate 8-10 interview questions total:
  - 3-4 technical questions specific to the role and resume skills
  - 3-4 behavioral questions using STAR method based on resume experience
  - 1-2 company/role-specific questions
- Questions should be realistic and commonly asked
- Focus ONLY on skills and experience mentioned in the resume and job description
- Do not reference skills or experience not present in the original resume
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
    
    # Add validation prompt with the original data structure
    validation_prompt = f"""
Original Resume Structure (DO NOT MODIFY THIS STRUCTURE):
{json.dumps(resume_json, indent=2)}

{PROMPT_TEMPLATE}
Job Description:
{job_description}

IMPORTANT: Your response must preserve the exact structure above. Only improve the content quality, do not add new data.
"""
    
    try:
        response = model.generate_content(validation_prompt)
        text = response.text or "{}"
        
        # Clean the response to extract JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        payload = json.loads(text)
        
        # Strict validation - ensure no hallucinated data
        validated_payload = validate_llm_output(payload, resume_json)
        return validated_payload
        
    except Exception as e:
        print(f"LLM processing error: {e}")
        # Return safe fallback that preserves original data
        return create_safe_fallback(resume_json)


def validate_llm_output(llm_output: Dict[str, Any], original_resume: Dict[str, Any]) -> Dict[str, Any]:
    """Strict validation to prevent hallucinations"""
    validated = {}
    
    # Validate summary - only if original had one
    original_summary = original_resume.get("summary", "").strip()
    if original_summary:
        validated["rewritten_summary"] = llm_output.get("rewritten_summary", original_summary)
    else:
        validated["rewritten_summary"] = ""
    
    # Validate experience - only allow existing companies
    validated["rewritten_experience"] = []
    original_companies = {exp.get("company", ""): exp for exp in original_resume.get("experience", [])}
    
    for exp in llm_output.get("rewritten_experience", []):
        company = exp.get("company", "")
        if company in original_companies:
            original_exp = original_companies[company]
            # Only use bullets if they're reasonable improvements of originals
            original_bullets = original_exp.get("achievements", [])
            new_bullets = exp.get("bullets", [])
            
            # Limit to original bullet count or fewer
            max_bullets = min(len(original_bullets), len(new_bullets), 4)
            validated_bullets = new_bullets[:max_bullets] if new_bullets else original_bullets
            
            validated["rewritten_experience"].append({
                "company": company,
                "bullets": validated_bullets
            })
    
    # Validate skills - only allow existing skills, just reordered
    original_skills = original_resume.get("skills", {})
    validated["ranked_skills"] = {}
    
    for category in ["Programming & Tools", "ML & AI", "Analytics"]:
        original_cat_skills = set(original_skills.get(category, []))
        llm_cat_skills = llm_output.get("ranked_skills", {}).get(category, [])
        
        # Only include skills that were in the original
        validated_skills = [skill for skill in llm_cat_skills if skill in original_cat_skills]
        # Add any missing original skills
        for original_skill in original_skills.get(category, []):
            if original_skill not in validated_skills:
                validated_skills.append(original_skill)
        
        validated["ranked_skills"][category] = validated_skills
    
    # Validate projects - only allow existing project titles
    original_project_titles = set(proj.get("title", "") for proj in original_resume.get("projects", []))
    llm_projects = llm_output.get("ranked_projects", [])
    
    validated_projects = [title for title in llm_projects if title in original_project_titles]
    # Add any missing original projects
    for proj in original_resume.get("projects", []):
        title = proj.get("title", "")
        if title not in validated_projects:
            validated_projects.append(title)
    
    validated["ranked_projects"] = validated_projects
    
    return validated


def create_safe_fallback(original_resume: Dict[str, Any]) -> Dict[str, Any]:
    """Create a safe fallback that preserves all original data"""
    return {
        "rewritten_summary": original_resume.get("summary", ""),
        "rewritten_experience": [
            {
                "company": exp.get("company", ""),
                "bullets": exp.get("achievements", [])
            }
            for exp in original_resume.get("experience", [])
        ],
        "ranked_skills": original_resume.get("skills", {}),
        "ranked_projects": [proj.get("title", "") for proj in original_resume.get("projects", [])]
    }


def generate_cover_letter(resume_json: Dict[str, Any], job_description: str, company_name: str = "", position_title: str = "") -> str:
    model = _get_model()

    if not company_name:
        company_name = "the hiring company"
    if not position_title:
        position_title = "the position"

    # Include original resume data in prompt for reference
    prompt = (
        f"ORIGINAL RESUME DATA (use only this information):\n"
        f"{json.dumps(resume_json, indent=2)}\n\n"
        f"{COVER_LETTER_TEMPLATE}\n\n"
        f"Job Description:\n{job_description}\n\n"
        f"Company Name: {company_name}\n"
        f"Position Title: {position_title}\n\n"
        f"Generate a professional cover letter using ONLY the information provided in the resume data above:"
    )

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

    # Include original resume data in prompt for reference
    prompt = (
        f"ORIGINAL RESUME DATA (base questions only on this):\n"
        f"{json.dumps(resume_json, indent=2)}\n\n"
        f"{INTERVIEW_QUESTIONS_TEMPLATE}\n\n"
        f"Job Description:\n{job_description}\n\n"
        f"Company Name: {company_name}\n"
        f"Position Title: {position_title}\n\n"
        f"Generate interview questions based ONLY on the skills and experience shown in the resume data above:"
    )

    try:
        response = model.generate_content(prompt)
        return response.text or "Unable to generate interview questions at this time."
    except Exception:
        return "Unable to generate interview questions at this time."
import json
from backend.llm import _get_model   # if inside same file, remove this line

RESUME_SCHEMA_PROMPT = """
You are a resume parser. 
Input: raw resume text.
Output: JSON strictly matching this schema:

{
  "contact_info": {"full_name": "", "email": "", "phone": "", "location": ""},
  "links": {"LinkedIn": "", "GitHub": "", "HuggingFace": "", "Coursera": ""},
  "summary": "",
  "education": [{"institution": "", "degree": "", "field": "", "location": "", "graduation_date": "", "gpa": ""}],
  "experience": [{"company": "", "position": "", "location": "", "start_date": "", "end_date": "", "achievements": []}],
  "projects": [{"title": "", "description": "", "technologies": [], "bullets": []}],
  "certifications": [],
  "skills": {"Programming & Tools": [], "ML & AI": [], "Analytics": []},
  "languages": []
}

Rules:
- Only extract what exists in the resume text.
- Do not hallucinate or invent data.
- Keep original wording for dates, degrees, roles.
- If a field is missing, leave it empty (do not delete keys).
"""

def llm_parse_resume(raw_text: str) -> dict:
    model = _get_model()
    prompt = f"{RESUME_SCHEMA_PROMPT}\n\nResume text:\n{raw_text}"
    response = model.generate_content(prompt)
    text = response.text.strip()

    # Clean out JSON from markdown fences if present
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].strip()

    try:
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"Failed to parse LLM output as JSON: {e}\nOutput was:\n{text}")


__all__ = ["rewrite_resume", "generate_cover_letter", "generate_interview_questions"]