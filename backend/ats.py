from typing import Dict, Any, List, Tuple
import math
import re


def _tokenize(text: str) -> List[str]:
    import re
    return [t.lower() for t in re.findall(r"[A-Za-z0-9+#.]+", text)]


def _flatten_resume(resume_json: dict) -> str:
    """
    Flatten nested resume JSON into a plain text string for keyword matching.
    Ensures lists are joined into strings.
    """
    parts = []

    # Contact info
    ci = resume_json.get("contact_info", {})
    parts.extend([ci.get("full_name", ""), ci.get("email", ""), ci.get("phone", ""), ci.get("location", "")])

    # Links
    links = resume_json.get("links", {})
    parts.extend([str(v) for v in links.values() if v])

    # Summary
    parts.append(resume_json.get("summary", ""))

    # Education
    for edu in resume_json.get("education", []):
        parts.extend([
            edu.get("institution", ""),
            edu.get("degree", ""),
            edu.get("field", ""),
            edu.get("location", ""),
            edu.get("graduation_date", ""),
            edu.get("gpa", "")
        ])

    # Experience
    for exp in resume_json.get("experience", []):
        parts.extend([
            exp.get("company", ""),
            exp.get("position", ""),
            exp.get("location", ""),
            exp.get("start_date", ""),
            exp.get("end_date", "")
        ])
        parts.extend(exp.get("achievements", []))  # achievements is a list

    # Projects
    for proj in resume_json.get("projects", []):
        parts.extend([
            proj.get("title", ""),
            proj.get("description", "")
        ])
        parts.extend(proj.get("technologies", []))
        parts.extend(proj.get("bullets", []))

    # Certifications
    parts.extend(resume_json.get("certifications", []))

    # Skills
    skills = resume_json.get("skills", {})
    for cat, items in skills.items():
        parts.append(cat)
        parts.extend(items)

    # Languages
    parts.extend(resume_json.get("languages", []))

    # Join everything as a string
    return " \n ".join([str(p) for p in parts if p])


def _extract_years_experience(start_date: str, end_date: str) -> float:
    """Extract years of experience from date strings"""
    import re
    from datetime import datetime

    # Try to extract years from date strings
    current_year = datetime.now().year

    def extract_year(date_str: str) -> int:
        year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
        if year_match:
            return int(year_match.group())
        # Handle "Present", "Current", etc.
        if re.search(r'(?i)(present|current|now)', date_str):
            return current_year
        return current_year

    if start_date:
        start_year = extract_year(start_date)
        end_year = extract_year(end_date) if end_date else current_year
        return max(0, end_year - start_year)
    return 0.5  # Default to 6 months if no dates


def _calculate_title_similarity(resume_json: Dict[str, Any], job_description: str) -> float:
    """Enhanced title similarity calculation"""
    import re

    # Extract job titles from resume
    resume_titles = []
    for exp in resume_json.get("experience", []):
        if exp.get("position"):
            resume_titles.append(exp["position"].lower())

    # Extract target job title from JD
    jd_lower = job_description.lower()

    # Common job title patterns
    title_patterns = [
        r'(?:position|role|job|title):\s*([^\n\r,]+)',
        r'(?:seeking|hiring|looking for)\s+(?:a\s+)?([^\n\r,]+?)(?:\s+to|\s+with|\s+who)',
        r'([^\n\r,]+?)\s*(?:position|role|opportunity)',
        r'we are hiring\s+(?:a\s+)?([^\n\r,]+)',
    ]

    jd_title_tokens = set()
    for pattern in title_patterns:
        matches = re.findall(pattern, jd_lower)
        for match in matches:
            jd_title_tokens.update(_tokenize(match.strip()))

    # If no specific pattern found, look for common job titles
    if not jd_title_tokens:
        common_titles = [
            "data scientist", "machine learning engineer", "software engineer",
            "data engineer", "analyst", "developer", "manager", "director",
            "senior", "junior", "lead", "principal", "staff"
        ]
        for title in common_titles:
            if title in jd_lower:
                jd_title_tokens.update(_tokenize(title))

    if not jd_title_tokens:
        return 0.5  # Neutral score if no title found

    # Calculate similarity with resume titles
    resume_title_tokens = set()
    for title in resume_titles:
        resume_title_tokens.update(_tokenize(title))

    overlap = len(jd_title_tokens & resume_title_tokens)
    return overlap / len(jd_title_tokens) if jd_title_tokens else 0


def _categorize_keywords(tokens: set) -> Tuple[List[str], List[str]]:
    """Better categorization of technical vs business keywords"""

    technical_indicators = {
        'python', 'java', 'javascript', 'sql', 'react', 'nodejs', 'aws', 'docker',
        'kubernetes', 'tensorflow', 'pytorch', 'pandas', 'numpy', 'git', 'linux',
        'mongodb', 'postgresql', 'redis', 'spark', 'hadoop', 'tableau', 'powerbi',
        'machine learning', 'deep learning', 'api', 'rest', 'graphql', 'microservices',
        'ci/cd', 'devops', 'cloud', 'database', 'algorithm', 'framework', 'library'
    }

    business_indicators = {
        'agile', 'scrum', 'project', 'management', 'leadership', 'communication',
        'collaboration', 'stakeholder', 'strategy', 'analysis', 'business',
        'requirements', 'planning', 'coordination', 'presentation', 'documentation'
    }

    technical = []
    business = []

    for token in tokens:
        token_lower = token.lower()
        if any(tech in token_lower for tech in technical_indicators):
            technical.append(token)
        elif any(biz in token_lower for biz in business_indicators):
            business.append(token)
        elif re.match(r'^[A-Z]+$', token) or re.match(r'^\w+\.\w+', token):
            technical.append(token)  # Acronyms or file extensions
        else:
            business.append(token)

    return technical, business


def score_ats(resume_json: Dict[str, Any], job_description: str) -> Dict[str, Any]:
    # Guard clause: check for empty or malformed resume JSON
    if not resume_json or not isinstance(resume_json, dict):
        return {
            "ats_score": 0,
            "keyword_matches": {"technical": [], "business": []},
            "missing_keywords": [],
            "recommendations": ["Resume JSON is empty or malformed"],
            "score_breakdown": {"skills": 0, "keywords": 0, "title": 0, "experience": 0}
        }

    resume_text = _flatten_resume(resume_json)

    # Check if resume has meaningful content
    if not resume_text.strip() or len(resume_text.strip()) < 20:
        return {
            "ats_score": 0,
            "keyword_matches": {"technical": [], "business": []},
            "missing_keywords": [],
            "recommendations": ["Empty or insufficient resume content"],
            "score_breakdown": {"skills": 0, "keywords": 0, "title": 0, "experience": 0}
        }

    # Enhanced weights per spec
    weights = {
        "skills": 0.40,
        "keywords": 0.30,
        "title": 0.20,
        "experience": 0.10,
    }

    resume_tokens = set(_tokenize(resume_text))
    jd_tokens = set(_tokenize(job_description))

    # Enhanced Skills overlap with better scoring
    skills_flat = set()
    for items in (resume_json.get("skills", {}) or {}).values():
        for s in items:
            for tok in _tokenize(s):
                skills_flat.add(tok)

    skills_overlap = len(skills_flat & jd_tokens)
    # Use JD tokens as baseline for relevance scoring
    skills_total = max(1, len(jd_tokens))
    skills_score = min(1.0, skills_overlap / max(1, skills_total * 0.3))  # Expect 30% skill match

    # Enhanced Keyword overlap
    keyword_overlap = len(resume_tokens & jd_tokens)
    keyword_total = max(1, len(jd_tokens))
    keyword_score = keyword_overlap / keyword_total

    # Enhanced Title similarity
    title_score = _calculate_title_similarity(resume_json, job_description)

    # Enhanced Experience calculation
    total_years = 0
    for exp in resume_json.get("experience", []):
        years = _extract_years_experience(exp.get("start_date", ""), exp.get("end_date", ""))
        total_years += years

    # Scale experience score based on typical requirements (2-8 years)
    exp_score = min(1.0, total_years / 5.0)

    total = (
        skills_score * weights["skills"]
        + keyword_score * weights["keywords"]
        + title_score * weights["title"]
        + exp_score * weights["experience"]
    )
    ats_score = max(0, min(100, round(total * 100)))

    # Enhanced Recommendations
    missing_keywords = list(jd_tokens - resume_tokens)
    recommendations: List[str] = []

    if skills_score < 0.6:
        recommendations.append("Add more technical skills relevant to the job description")
    if keyword_score < 0.4:
        recommendations.append("Include more keywords from the job description in your experience bullets")
    if title_score < 0.4:
        recommendations.append("Consider adjusting your job titles to better match the target role")
    if exp_score < 0.4:
        recommendations.append("Highlight your years of experience and specific project durations")
    if total_years < 2:
        recommendations.append("Emphasize relevant projects, internships, or coursework to strengthen experience")

    # Better keyword categorization
    matched_keywords = list(resume_tokens & jd_tokens)
    technical, business = _categorize_keywords(matched_keywords)

    return {
        "ats_score": ats_score,
        "keyword_matches": {"technical": technical[:20], "business": business[:20]},
        "missing_keywords": missing_keywords[:15],
        "recommendations": recommendations,
        "score_breakdown": {
            "skills": round(skills_score * 100),
            "keywords": round(keyword_score * 100),
            "title": round(title_score * 100),
            "experience": round(exp_score * 100)
        }
    }


__all__ = ["score_ats"]


