import json
import os
import re
from typing import Dict, List, Any

from PyPDF2 import PdfReader
from docx import Document as DocxDocument
from PIL import Image
import pytesseract


def _sanitize_text(text: str) -> str:
    """Sanitize text to be XML-compatible by removing NULL bytes and control characters."""
    if not text:
        return ""

    # Remove NULL bytes and control characters except for common whitespace
    # Keep tabs (\t), newlines (\n), and carriage returns (\r)
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # Replace multiple whitespaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)

    # Strip leading/trailing whitespace
    sanitized = sanitized.strip()

    # Ensure we return valid Unicode string
    return sanitized


def _sanitize_nested_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sanitize nested list of dictionaries (education, experience, projects)."""
    sanitized = []
    for item in data:
        sanitized_item = {}
        for key, value in item.items():
            if isinstance(value, str):
                sanitized_item[key] = _sanitize_text(value)
            elif isinstance(value, list):
                sanitized_item[key] = [_sanitize_text(v) if isinstance(v, str) else v for v in value]
            else:
                sanitized_item[key] = value
        sanitized.append(sanitized_item)
    return sanitized


def _sanitize_skills_data(skills: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Sanitize skills dictionary."""
    sanitized = {}
    for category, skill_list in skills.items():
        sanitized[_sanitize_text(category)] = [_sanitize_text(skill) for skill in skill_list]
    return sanitized


def _sanitize_contact_info(contact: Dict[str, str]) -> Dict[str, str]:
    """Sanitize contact information dictionary."""
    sanitized = {}
    for key, value in contact.items():
        sanitized[key] = _sanitize_text(value) if isinstance(value, str) else value
    return sanitized


def _empty_resume_json() -> Dict[str, Any]:
    return {
        "contact_info": {
            "full_name": "",
            "email": "",
            "phone": "",
            "location": "",
        },
        "links": {
            "LinkedIn": "",
            "GitHub": "",
            "HuggingFace": "",
            "Coursera": "",
        },
        "summary": "",
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "skills": {
            "Programming & Tools": [],
            "ML & AI": [],
            "Analytics": [],
        },
        "languages": [],
    }


def _extract_text_from_pdf(file_path: str) -> str:
    import re
    
    reader = PdfReader(file_path)
    texts: List[str] = []
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
            if page_text:
                texts.append(page_text)
        except Exception:
            continue
    
    full_text = "\n".join(texts)
    
    # Clean up the extracted text - remove PDF metadata and technical content
    lines = full_text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        # Skip lines that look like PDF metadata
        if any(skip in line.lower() for skip in [
            'xmlns:', 'rdf:', 'dc:', 'xmpmeta', 'xpacket', 'endstream', 
            'endobj', 'xref', 'trailer', 'startxref', '%%eof', 'flowcv',
            'creator', 'seq', 'li', 'description', 'rdf', 'xmp', 'metadata',
            'pdf', 'adobe', 'producer', 'creationdate', 'moddate'
        ]):
            continue
        # Skip very short lines that are likely artifacts
        if len(line) < 3:
            continue
        # Skip lines that are mostly special characters or numbers
        if len(re.sub(r'[^\w\s]', '', line)) < len(line) * 0.3:
            continue
        # Skip lines that are just numbers or dates
        if re.match(r'^[\d\s\-/\.]+$', line):
            continue
        cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def _extract_text_from_docx(file_path: str) -> str:
    doc = DocxDocument(file_path)
    return "\n".join(p.text for p in doc.paragraphs)


def _extract_text_from_image(file_path: str) -> str:
    image = Image.open(file_path)
    return pytesseract.image_to_string(image)


def _extract_text_from_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def _guess_basic_contact(text: str) -> Dict[str, str]:
    import re

    email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    
    # Enhanced phone number detection including Indian formats
    phone_patterns = [
        r'\+91[-\s]?[6-9]\d{9}',  # Indian mobile format
        r'(\+?1?[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})',  # US format
        r'(\+\d{1,3}[-.\s]?)?\(?([0-9]{2,4})\)?[-.\s]?([0-9]{2,4})[-.\s]?([0-9]{2,4})',  # International
        r'(\d{10,})',  # Just digits
    ]
    
    phone_match = None
    for pattern in phone_patterns:
        phone_match = re.search(pattern, text)
        if phone_match:
            break
    
    # Better name detection - look for the first line that looks like a name
    full_name = ""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for line in lines[:5]:  # Check first 5 lines
        # Skip lines that are clearly not names
        if any(skip in line.lower() for skip in [
            'email', 'phone', 'address', 'resume', 'cv', 'curriculum', 'vitae',
            'objective', 'summary', 'profile', 'experience', 'education'
        ]):
            continue
        # Look for lines that look like names (2-4 words, mostly letters, reasonable length)
        words = line.split()
        if (2 <= len(words) <= 4 and 
            len(line) <= 60 and 
            all(word.replace('-', '').replace("'", '').isalpha() for word in words) and
            not any(char.isdigit() for char in line)):
            full_name = line
            break
    
    # Enhanced location detection
    location = ""
    location_patterns = [
        r'([A-Z][a-z]+,?\s+[A-Z][a-z]+,?\s+\d{5,6})',  # City, State ZIP
        r'([A-Z][a-z]+\s+\([A-Z]\)\s*•\s*[A-Z][a-z]+\s+\d{5,6})',  # Mumbai (E) • Mumbai 400071
        r'([A-Z][a-z]+,?\s+[A-Z][a-z]+)',  # City, State
        r'([A-Z][a-z]+\s+\d{5,6})',  # City ZIP
    ]

    for pattern in location_patterns:
        loc_match = re.search(pattern, text)
        if loc_match:
            location = loc_match.group(1)
            break

    # Try to extract location from address line
    if not location:
        for line in lines[:10]:
            if any(indicator in line.lower() for indicator in ['address', 'mumbai', 'delhi', 'bangalore', 'hyderabad', 'pune', 'chennai']):
                # Extract city and country/state
                if '•' in line:
                    parts = [p.strip() for p in line.split('•')]
                    for part in parts:
                        if any(city in part.lower() for city in ['mumbai', 'delhi', 'bangalore', 'hyderabad', 'pune', 'chennai']) or re.search(r'\d{5,6}', part):
                            location = part
                            break
                break

    return {
        "full_name": full_name,
        "email": email_match.group(0) if email_match else "",
        "phone": phone_match.group(0) if phone_match else "",
        "location": location,
    }


def _extract_sections(text: str) -> Dict[str, Any]:
    """Extract structured sections from resume text"""
    import re
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    sections = {
        "summary": "",
        "education": [],
        "experience": [],
        "projects": [],
        "certifications": [],
        "skills": {"Programming & Tools": [], "ML & AI": [], "Analytics": []},
        "languages": []
    }
    
    current_section = None
    current_item = {}
    
    for i, line in enumerate(lines):
        line_lower = line.lower()
        
        # Detect section headers
        if any(keyword in line_lower for keyword in ['summary', 'objective', 'profile', 'about']):
            # Save current item before switching sections
            if current_item and current_section in ['education', 'experience', 'projects']:
                if current_section == 'education':
                    sections['education'].append(current_item)
                elif current_section == 'experience':
                    sections['experience'].append(current_item)
                elif current_section == 'projects':
                    sections['projects'].append(current_item)
            current_section = 'summary'
            current_item = {}
            continue
        elif any(keyword in line_lower for keyword in ['education', 'academic']):
            # Save current item before switching sections
            if current_item and current_section in ['education', 'experience', 'projects']:
                if current_section == 'education':
                    sections['education'].append(current_item)
                elif current_section == 'experience':
                    sections['experience'].append(current_item)
                elif current_section == 'projects':
                    sections['projects'].append(current_item)
            current_section = 'education'
            current_item = {}
            continue
        elif any(keyword in line_lower for keyword in ['experience', 'work history', 'employment', 'career']):
            # Save current item before switching sections
            if current_item and current_section in ['education', 'experience', 'projects']:
                if current_section == 'education':
                    sections['education'].append(current_item)
                elif current_section == 'experience':
                    sections['experience'].append(current_item)
                elif current_section == 'projects':
                    sections['projects'].append(current_item)
            current_section = 'experience'
            current_item = {}
            continue
        elif any(keyword in line_lower for keyword in ['project', 'portfolio']):
            # Save current item before switching sections
            if current_item and current_section in ['education', 'experience', 'projects']:
                if current_section == 'education':
                    sections['education'].append(current_item)
                elif current_section == 'experience':
                    sections['experience'].append(current_item)
                elif current_section == 'projects':
                    sections['projects'].append(current_item)
            current_section = 'projects'
            current_item = {}
            continue
        elif any(keyword in line_lower for keyword in ['certification', 'certificate', 'license']):
            current_section = 'certifications'
            current_item = {}
            continue
        elif any(keyword in line_lower for keyword in ['skill', 'technical', 'competenc']):
            current_section = 'skills'
            current_item = {}
            continue
        elif any(keyword in line_lower for keyword in ['language']):
            current_section = 'languages'
            current_item = {}
            continue
        
        # Process content based on current section
        if current_section == 'summary' and line and not any(keyword in line_lower for keyword in ['education', 'experience', 'project', 'skill']):
            sections['summary'] += line + " "
        
        elif current_section == 'education':
            # Enhanced education parsing for formats like "MICA Ahmedabad, Gujarat"
            if any(keyword in line_lower for keyword in ['university', 'college', 'institute', 'school', 'mica', 'nit', 'iit', 'iim']):
                if current_item:
                    sections['education'].append(current_item)

                # Parse institution and location from same line
                institution = line
                location = ""
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) >= 2:
                        institution = parts[0]
                        location = ', '.join(parts[1:])

                current_item = {
                    "institution": institution,
                    "degree": "",
                    "field": "",
                    "location": location,
                    "graduation_date": "",
                    "gpa": ""
                }
            elif current_item and re.search(r'\b(bachelor|master|phd|doctorate|associate|diploma|degree|pgdm|b\.tech|m\.tech|mba)\b', line_lower):
                # Parse degree line like "PGDM-C, Advertising and Brand Management, Digital Marketing"
                current_item['degree'] = line
                # Extract field from degree line
                if ',' in line:
                    parts = [p.strip() for p in line.split(',')]
                    if len(parts) > 1:
                        current_item['field'] = ', '.join(parts[1:])
            elif current_item and re.search(r'\b(20\d{2}|19\d{2})\b', line):
                # Parse date ranges like "2017-19" or "2010-14"
                current_item['graduation_date'] = line
            elif current_item and re.search(r'\b\d+\.\d+\b', line):
                current_item['gpa'] = line
            elif current_item and 'dissertation' in line_lower:
                # Handle dissertation info
                if not current_item['field']:
                    current_item['field'] = line
        
        elif current_section == 'experience':
            # Enhanced experience parsing for formats like "Publicis Commerce Mumbai, Maharashtra"
            if any(keyword in line_lower for keyword in ['commerce', 'advisory', 'consulting', 'technologies', 'systems', 'solutions', 'pvt', 'ltd', 'inc', 'corp', 'llc']) or \
               re.search(r'\b(publicis|pwc|microsoft|google|amazon|facebook|apple)\b', line_lower):
                if current_item:
                    sections['experience'].append(current_item)

                # Parse company and location from same line
                company = line
                location = ""
                if any(city in line_lower for city in ['mumbai', 'delhi', 'bangalore', 'hyderabad', 'pune', 'chennai', 'new york', 'san francisco', 'seattle']):
                    # Try to split company and location
                    parts = re.split(r'\s{2,}|\t', line)  # Split on multiple spaces or tabs
                    if len(parts) >= 2:
                        company = parts[0]
                        location = parts[-1]

                current_item = {
                    "company": company,
                    "position": "",
                    "location": location,
                    "start_date": "",
                    "end_date": "",
                    "achievements": []
                }
            elif current_item and any(keyword in line_lower for keyword in ['director', 'manager', 'engineer', 'developer', 'analyst', 'specialist', 'associate', 'consultant', 'lead', 'senior']):
                # Handle position with date range like "Director – D2C Commerce Apr 2024 – May 2025"
                position_line = line
                current_item['position'] = position_line

                # Extract dates from position line
                date_pattern = r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}\s*[–-]\s*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|present)\s*\d{0,4}'
                date_match = re.search(date_pattern, line_lower)
                if date_match:
                    date_range = date_match.group(0)
                    if '–' in date_range or '-' in date_range:
                        dates = re.split(r'\s*[–-]\s*', date_range)
                        if len(dates) >= 2:
                            current_item['start_date'] = dates[0].strip()
                            current_item['end_date'] = dates[1].strip()
                    # Clean position title by removing date
                    current_item['position'] = re.sub(date_pattern, '', line, flags=re.IGNORECASE).strip()
            elif current_item and (line.startswith('•') or line.startswith('-') or line.startswith('*')):
                achievement = line[1:].strip()
                if achievement:  # Only add non-empty achievements
                    current_item['achievements'].append(achievement)
            elif current_item and re.search(r'\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}', line_lower):
                # Handle standalone date lines
                if not current_item['start_date']:
                    current_item['start_date'] = line
                elif not current_item['end_date']:
                    current_item['end_date'] = line
        
        elif current_section == 'projects':
            if line and not line.startswith('•') and not line.startswith('-'):
                if current_item:
                    sections['projects'].append(current_item)
                current_item = {
                    "title": line,
                    "description": "",
                    "technologies": [],
                    "bullets": []
                }
            elif current_item and (line.startswith('•') or line.startswith('-') or line.startswith('*')):
                current_item['bullets'].append(line[1:].strip())
            elif current_item and any(tech in line_lower for tech in ['python', 'java', 'javascript', 'react', 'node', 'sql', 'tensorflow', 'pytorch']):
                current_item['technologies'].extend([tech.strip() for tech in line.split(',')])
        
        elif current_section == 'certifications':
            if line and not line.startswith('•'):
                sections['certifications'].append(line)
        
        elif current_section == 'skills':
            # Enhanced skills extraction with better categorization
            if ',' in line or '|' in line:
                # Handle both comma and pipe separated skills
                separator = ',' if ',' in line else '|'
                skills = [skill.strip() for skill in line.split(separator) if skill.strip()]
                for skill in skills:
                    # Clean up skill name (remove category prefixes)
                    clean_skill = skill
                    for category in ['Programming & Tools:', 'ML & AI:', 'Analytics:', 'Technical:', 'Languages:']:
                        if skill.startswith(category):
                            clean_skill = skill.replace(category, '').strip()
                            break

                    # Enhanced categorization
                    if any(tech in clean_skill.lower() for tech in [
                        'python', 'java', 'javascript', 'sql', 'git', 'docker', 'kubernetes',
                        'linux', 'aws', 'azure', 'gcp', 'react', 'node', 'html', 'css', 'c++', 'r'
                    ]):
                        sections['skills']['Programming & Tools'].append(clean_skill)
                    elif any(tech in clean_skill.lower() for tech in [
                        'tensorflow', 'pytorch', 'scikit-learn', 'machine learning', 'ai', 'neural',
                        'deep learning', 'nlp', 'computer vision', 'bert', 'gpt', 'xgboost'
                    ]):
                        sections['skills']['ML & AI'].append(clean_skill)
                    elif any(tech in clean_skill.lower() for tech in [
                        'analytics', 'statistics', 'excel', 'tableau', 'power bi', 'spark',
                        'hadoop', 'pandas', 'numpy', 'matplotlib', 'seaborn', 'plotly'
                    ]):
                        sections['skills']['Analytics'].append(clean_skill)
                    else:
                        # Default to Programming & Tools if unsure
                        sections['skills']['Programming & Tools'].append(clean_skill)
            else:
                # Single skill or category header
                if ':' in line:
                    # This is a category header like "Programming & Tools: Python, SQL"
                    category_part, skills_part = line.split(':', 1)
                    category_name = category_part.strip()
                    if skills_part.strip():
                        skills = [skill.strip() for skill in skills_part.split(',') if skill.strip()]
                        if any(keyword in category_name.lower() for keyword in ['programming', 'tools', 'technical', 'language']):
                            sections['skills']['Programming & Tools'].extend(skills)
                        elif any(keyword in category_name.lower() for keyword in ['ml', 'ai', 'machine', 'learning']):
                            sections['skills']['ML & AI'].extend(skills)
                        elif any(keyword in category_name.lower() for keyword in ['analytics', 'analysis', 'data']):
                            sections['skills']['Analytics'].extend(skills)
                        else:
                            sections['skills']['Programming & Tools'].extend(skills)
                elif line.strip() and not any(section_word in line.lower() for section_word in ['education', 'experience', 'project', 'certification']):
                    # Single skill line
                    if any(tech in line.lower() for tech in ['python', 'java', 'sql', 'git']):
                        sections['skills']['Programming & Tools'].append(line.strip())
                    elif any(tech in line.lower() for tech in ['tensorflow', 'machine learning', 'ai']):
                        sections['skills']['ML & AI'].append(line.strip())
                    elif any(tech in line.lower() for tech in ['analytics', 'tableau', 'excel']):
                        sections['skills']['Analytics'].append(line.strip())
                    else:
                        sections['skills']['Programming & Tools'].append(line.strip())
        
        elif current_section == 'languages':
            if ',' in line:
                sections['languages'].extend([lang.strip() for lang in line.split(',')])
            elif line:
                sections['languages'].append(line)
    
    # Add the last item if exists
    if current_item:
        if current_section == 'education':
            sections['education'].append(current_item)
        elif current_section == 'experience':
            sections['experience'].append(current_item)
        elif current_section == 'projects':
            sections['projects'].append(current_item)
    
    return sections


def parse_resume(file_path: str) -> Dict[str, Any]:
    """
    Parse a resume file (PDF/DOCX/TXT/Image) into the immutable JSON schema.

    This is a lightweight heuristic parser to bootstrap the schema. It prioritizes
    not dropping data by keeping empty sections when unknown.
    """
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".pdf"]:
        raw_text = _extract_text_from_pdf(file_path)
    elif ext in [".docx"]:
        raw_text = _extract_text_from_docx(file_path)
    elif ext in [".png", ".jpg", ".jpeg", ".tiff", ".bmp"]:
        raw_text = _extract_text_from_image(file_path)
    else:
        raw_text = _extract_text_from_txt(file_path)

    # Sanitize the raw text to remove XML-incompatible characters
    raw_text = _sanitize_text(raw_text)

    data = _empty_resume_json()
    data["contact_info"] = _guess_basic_contact(raw_text)

    # Extract structured sections
    sections = _extract_sections(raw_text)

    # Merge extracted sections with the base structure and sanitize all text
    data["summary"] = _sanitize_text(sections["summary"].strip())
    data["education"] = _sanitize_nested_data(sections["education"])
    data["experience"] = _sanitize_nested_data(sections["experience"])
    data["projects"] = _sanitize_nested_data(sections["projects"])
    data["certifications"] = [_sanitize_text(cert) for cert in sections["certifications"]]
    data["skills"] = _sanitize_skills_data(sections["skills"])
    data["languages"] = [_sanitize_text(lang) for lang in sections["languages"]]

    # Sanitize contact info as well
    data["contact_info"] = _sanitize_contact_info(data["contact_info"])

    return data


__all__ = ["parse_resume"]


