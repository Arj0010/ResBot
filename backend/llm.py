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
3. Reorder EXISTING skills by relevance to job description (keep same categories)
4. Reorder EXISTING projects by relevance (do not add or remove projects)
5. Reorder EXISTING experience by relevance to job description

Quality Guidelines:
- Each experience bullet should be ≤1.5 lines for ATS compatibility
- Use action verbs and quantify results where original data supports it
- Focus on achievements over responsibilities
- Ensure bullets start with strong action verbs

Constraints:
- Maximum 3-4 bullets per experience entry (use the most impactful existing ones)
- If original has fewer bullets, don't add more
- Return ONLY data that was in the original resume
- Preserve the EXACT same JSON structure as input
- Return the COMPLETE resume JSON with ALL original fields

Output: Return the complete resume JSON with optimizations applied but preserving all original structure and data.
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

    # Create optimization prompt
    prompt = f"""
Original Resume JSON:
{json.dumps(resume_json, indent=2)}

Job Description:
{job_description}

{PROMPT_TEMPLATE}

IMPORTANT: Return the COMPLETE resume JSON with the EXACT same structure as the input, but with optimizations applied.
"""

    try:
        response = model.generate_content(prompt)
        text = response.text or "{}"

        # Clean the response to extract JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]

        payload = json.loads(text)

        # Validate and merge with original to ensure completeness
        optimized_resume = validate_and_merge_resume(payload, resume_json)
        return optimized_resume

    except Exception as e:
        print(f"LLM processing error: {e}")
        # Return original data if optimization fails
        return resume_json


def validate_and_merge_resume(llm_output: Dict[str, Any], original_resume: Dict[str, Any]) -> Dict[str, Any]:
    """Validate LLM output and merge with original to ensure complete resume structure"""
    # Start with original resume as base
    result = original_resume.copy()

    # Validate and update summary if improved
    if llm_output.get("summary") and original_resume.get("summary"):
        result["summary"] = llm_output["summary"]

    # Validate and update experience if improved
    if llm_output.get("experience"):
        original_companies = {exp.get("company", ""): exp for exp in original_resume.get("experience", [])}
        validated_experience = []

        # Process LLM-optimized experience
        for llm_exp in llm_output["experience"]:
            company = llm_exp.get("company", "")
            if company in original_companies:
                # Merge optimized content with original structure
                original_exp = original_companies[company].copy()

                # Update achievements if provided and valid
                if llm_exp.get("achievements"):
                    # Limit bullets to reasonable count
                    max_bullets = min(len(llm_exp["achievements"]), 4)
                    original_exp["achievements"] = llm_exp["achievements"][:max_bullets]

                validated_experience.append(original_exp)
                # Remove from original_companies to track processed companies
                del original_companies[company]

        # Add any remaining companies that weren't processed by LLM
        for remaining_exp in original_companies.values():
            validated_experience.append(remaining_exp)

        result["experience"] = validated_experience

    # Validate and update skills if reordered
    if llm_output.get("skills"):
        original_skills = original_resume.get("skills", {})
        validated_skills = {}

        # Process each category from LLM output
        for category, skills in llm_output["skills"].items():
            if category in original_skills:
                # Only include skills that existed in original
                original_category_skills = set(original_skills[category])
                filtered_skills = [skill for skill in skills if skill in original_category_skills]

                # Add any missing original skills
                for orig_skill in original_skills[category]:
                    if orig_skill not in filtered_skills:
                        filtered_skills.append(orig_skill)

                validated_skills[category] = filtered_skills

        # Add any categories not processed by LLM
        for category, skills in original_skills.items():
            if category not in validated_skills:
                validated_skills[category] = skills

        result["skills"] = validated_skills

    # Validate and update projects if reordered
    if llm_output.get("projects"):
        original_projects = {proj.get("title", ""): proj for proj in original_resume.get("projects", [])}
        validated_projects = []

        # Process LLM-reordered projects
        for llm_proj in llm_output["projects"]:
            title = llm_proj.get("title", "")
            if title in original_projects:
                # Use original project data but with optimized bullets if provided
                original_proj = original_projects[title].copy()
                if llm_proj.get("bullets"):
                    max_bullets = min(len(llm_proj["bullets"]), 3)
                    original_proj["bullets"] = llm_proj["bullets"][:max_bullets]

                validated_projects.append(original_proj)
                del original_projects[title]

        # Add any remaining projects
        for remaining_proj in original_projects.values():
            validated_projects.append(remaining_proj)

        result["projects"] = validated_projects

    return result


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
  "skills": {"Technical": [], "Non-Technical": []},
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