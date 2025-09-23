import json
import re
import os
from typing import Dict, Any, List
from datetime import datetime

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH


def _safe_text(text: str) -> str:
    """Ensure text is safe for docx XML by removing any problematic characters."""
    if not text:
        return ""

    # Remove NULL bytes and control characters except for common whitespace
    sanitized = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)

    # Replace multiple whitespaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)

    # Strip leading/trailing whitespace
    sanitized = sanitized.strip()

    return sanitized


def _safe_add_paragraph(doc, text: str):
    """Safely add a paragraph with text sanitization."""
    safe_text = _safe_text(text)
    if safe_text:
        return doc.add_paragraph(safe_text)
    return doc.add_paragraph("")


def _add_hyperlink(paragraph, url: str, text: str):
    # Create hyperlink w:r element
    part = paragraph.part
    r_id = part.relate_to(url, reltype="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)

    new_run = OxmlElement('w:r')
    r_pr = OxmlElement('w:rPr')
    r_style = OxmlElement('w:rStyle')
    r_style.set(qn('w:val'), 'Hyperlink')
    r_pr.append(r_style)
    new_run.append(r_pr)

    t = OxmlElement('w:t')
    t.text = _safe_text(text)
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._p.append(hyperlink)


def render_harvard(resume_json: Dict[str, Any], output_path: str, template_config_path: str) -> str:
    """Generate DOCX resume with proper Harvard formatting"""
    try:
        doc = Document()

        # Set proper Harvard margins and font
        sections = doc.sections
        for section in sections:
            section.top_margin = Inches(1.0)
            section.bottom_margin = Inches(1.0)
            section.left_margin = Inches(0.5)
            section.right_margin = Inches(0.5)

        # Style configuration - Calibri 9pt for 6-company one-page layout
        style = doc.styles['Normal']
        style.font.name = 'Calibri'
        style.font.size = Pt(9)  # Reduced to 9pt for more space
        # Ultra-compact line spacing for 6 companies
        style.paragraph_format.line_spacing = 0.9
        style.paragraph_format.space_after = Pt(1)

        # Header - Name (centered) - compact for 6 companies
        contact = resume_json.get('contact_info', {})
        name_para = doc.add_paragraph()
        name_run = name_para.add_run(_safe_text(contact.get('full_name', 'NAME')))
        name_run.font.size = Pt(12)  # Further reduced for space
        name_run.font.bold = True
        name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name_para.paragraph_format.space_after = Pt(1)  # Minimal spacing

        # Contact line (centered)
        contact_para = doc.add_paragraph()
        contact_info = []
        links = resume_json.get('links', {})

        if contact.get('email'):
            contact_info.append(contact['email'])
        if contact.get('phone'):
            contact_info.append(contact['phone'])
        if links.get('LinkedIn'):
            contact_info.append('LinkedIn')
        if links.get('GitHub'):
            contact_info.append('GitHub')
        if links.get('HuggingFace'):
            contact_info.append('HuggingFace')

        contact_para.add_run(' • '.join(contact_info))
        contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_para.paragraph_format.space_after = Pt(3)  # Ultra-compact for 6 companies

        # Career Objective
        if resume_json.get('summary'):
            _add_section_docx(doc, "CAREER OBJECTIVE", resume_json['summary'])

        # Education
        if resume_json.get('education'):
            _add_education_section_docx(doc, resume_json['education'])

        # Experience
        if resume_json.get('experience'):
            _add_experience_section_docx(doc, resume_json['experience'])

        # Projects - only show if they exist in original resume, prioritize most relevant
        projects = resume_json.get('projects', [])
        if projects and len(projects) > 0:
            # Show 1-2 projects based on available space and relevance
            project_limit = 2 if len(projects) > 1 else 1
            _add_projects_section_docx(doc, projects[:project_limit])

        # Certificates
        if resume_json.get('certifications'):
            _add_certificates_section_docx(doc, resume_json['certifications'])

        # Skills
        if resume_json.get('skills'):
            _add_skills_section_docx(doc, resume_json['skills'])

        # Languages
        if resume_json.get('languages'):
            _add_languages_section_docx(doc, resume_json['languages'])

        # Save document
        doc.save(output_path)
        return output_path

    except Exception as e:
        print(f"DOCX generation error: {e}")
        return ""


def _add_section_docx(doc, title: str, content: str):
    """Add a section with title and content to DOCX"""
    # Section title
    title_para = doc.add_paragraph()
    title_run = title_para.add_run(title)
    title_run.font.bold = True
    title_run.font.size = Pt(10)  # Ultra-compact for 6 companies
    title_para.paragraph_format.space_before = Pt(3)  # Minimal spacing
    title_para.paragraph_format.space_after = Pt(0)

    # Divider line
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(1)  # Ultra-compact

    # Content
    content_para = doc.add_paragraph(_safe_text(content))
    content_para.paragraph_format.space_after = Pt(1)  # Ultra-compact


def _add_education_section_docx(doc, education_list):
    """Add education section to DOCX"""
    # Section title
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("EDUCATION")
    title_run.font.bold = True
    title_run.font.size = Pt(11)  # Reduced from 13pt
    title_para.paragraph_format.space_before = Pt(6)  # Reduced from 12pt

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)  # Reduced from 6pt

    # Education entries
    for edu in education_list:
        # Institution and date line
        table = doc.add_table(rows=1, cols=2)
        table.allow_autofit = True
        left_cell, right_cell = table.rows[0].cells

        # Institution (bold)
        inst_para = left_cell.paragraphs[0]
        inst_run = inst_para.add_run(_safe_text(edu.get('institution', '')))
        inst_run.font.bold = True

        # Date and location (right-aligned)
        date_para = right_cell.paragraphs[0]
        end_date = edu.get('graduation_date', '')
        location = edu.get('location', '')
        date_location = f"{end_date} | {location}" if end_date and location else (end_date or location)
        date_para.add_run(_safe_text(date_location))
        date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Degree line
        degree_para = doc.add_paragraph()
        degree_text = f"{edu.get('degree', '')} {edu.get('field', '')}".strip()
        if edu.get('gpa'):
            degree_text += f" – {edu['gpa']}"
        degree_para.add_run(_safe_text(degree_text))
        degree_para.paragraph_format.space_after = Pt(2)  # Reduced from 6pt


def _add_experience_section_docx(doc, experience_list):
    """Add experience section to DOCX"""
    # Section title
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("EXPERIENCE")
    title_run.font.bold = True
    title_run.font.size = Pt(11)  # Reduced from 13pt
    title_para.paragraph_format.space_before = Pt(6)  # Reduced from 12pt

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)  # Reduced from 6pt

    # Experience entries
    for exp in experience_list:
        # Position and date line
        table = doc.add_table(rows=1, cols=2)
        table.allow_autofit = True
        left_cell, right_cell = table.rows[0].cells

        # Position and company (bold)
        pos_para = left_cell.paragraphs[0]
        pos_run = pos_para.add_run(_safe_text(f"{exp.get('position', '')}, {exp.get('company', '')}"))
        pos_run.font.bold = True

        # Date and location (right-aligned)
        date_para = right_cell.paragraphs[0]
        start_date = exp.get('start_date', '')
        end_date = exp.get('end_date', 'Present')
        location = exp.get('location', '')
        date_location = f"{start_date} – {end_date} | {location}" if start_date and location else f"{start_date} – {end_date}"
        date_para.add_run(_safe_text(date_location))
        date_para.alignment = WD_ALIGN_PARAGRAPH.RIGHT

        # Smart bullet allocation for all 6 companies based on recency
        exp_index = experience_list.index(exp)
        if exp_index <= 1:  # Companies 1-2 (most recent): 3 bullets
            bullet_limit = 3
        elif exp_index <= 3:  # Companies 3-4 (mid-career): 2 bullets
            bullet_limit = 2
        else:  # Companies 5-6 (early career): 1-2 bullets
            bullet_limit = 1 if exp_index == 5 else 2

        for bullet in exp.get('achievements', [])[:bullet_limit]:
            bullet_para = doc.add_paragraph()
            bullet_para.add_run(f"• {_safe_text(bullet)}")
            bullet_para.paragraph_format.space_after = Pt(0.5)  # Ultra-compact for 6 companies

        # Space between jobs - minimal for 6 companies
        doc.add_paragraph().paragraph_format.space_after = Pt(1.5)  # Ultra-compact


def _add_projects_section_docx(doc, projects_list):
    """Add projects section to DOCX"""
    # Section title
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("PROJECTS")
    title_run.font.bold = True
    title_run.font.size = Pt(11)  # Reduced from 13pt
    title_para.paragraph_format.space_before = Pt(6)  # Reduced from 12pt

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)  # Reduced from 6pt

    # Project entries
    for project in projects_list:
        # Project title (bold)
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(_safe_text(project.get('title', '')))
        title_run.font.bold = True

        # Intelligent bullet allocation for projects
        project_index = projects_list.index(project)
        if len(projects_list) == 1:  # Single project - can afford more bullets
            bullet_limit = 3
        else:  # Multiple projects - limit bullets per project
            bullet_limit = 2

        for bullet in project.get('bullets', [])[:bullet_limit]:
            bullet_para = doc.add_paragraph()
            bullet_para.add_run(f"• {_safe_text(bullet)}")
            bullet_para.paragraph_format.space_after = Pt(1)  # Reduced spacing
            bullet_para.paragraph_format.left_indent = Inches(0.25)

        # Space between projects
        doc.add_paragraph().paragraph_format.space_after = Pt(2)  # Reduced from 6pt


def _add_certificates_section_docx(doc, certificates_list):
    """Add certificates section to DOCX"""
    # Section title
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("CERTIFICATES")
    title_run.font.bold = True
    title_run.font.size = Pt(11)  # Reduced from 13pt
    title_para.paragraph_format.space_before = Pt(6)  # Reduced from 12pt

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)  # Reduced from 6pt

    # Certificate entries - show all but in compact format
    for cert in certificates_list:
        cert_para = doc.add_paragraph()
        cert_text = _safe_text(cert) if isinstance(cert, str) else _safe_text(cert.get('name', ''))
        cert_para.add_run(f"• {cert_text}")  # Add bullet for consistency
        cert_para.paragraph_format.space_after = Pt(1)  # Reduced from 3pt


def _add_skills_section_docx(doc, skills_dict):
    """Add skills section to DOCX"""
    # Section title
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("SKILLS")
    title_run.font.bold = True
    title_run.font.size = Pt(11)  # Reduced from 13pt
    title_para.paragraph_format.space_before = Pt(6)  # Reduced from 12pt

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)  # Reduced from 6pt

    # Skill categories with Harvard formatting (parentheses)
    categories = {
        'Programming & Tools': 'Programming & Tools',
        'ML & AI': 'ML & AI',
        'Analytics': 'Analytics'
    }

    for key, title in categories.items():
        if skills_dict.get(key):
            # Category title (bold)
            cat_para = doc.add_paragraph()
            cat_run = cat_para.add_run(f"{title}:")
            cat_run.font.bold = True
            cat_para.paragraph_format.space_after = Pt(0)

            # Skills in parentheses format
            skills_para = doc.add_paragraph()
            skills_text = ' '.join([f"({_safe_text(skill)})" for skill in skills_dict[key]])
            skills_para.add_run(skills_text)
            skills_para.paragraph_format.space_after = Pt(2)  # Reduced from 6pt


def _add_languages_section_docx(doc, languages_list):
    """Add languages section to DOCX"""
    if not languages_list:
        return

    # Section title
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("LANGUAGES")
    title_run.font.bold = True
    title_run.font.size = Pt(11)  # Reduced from 13pt
    title_para.paragraph_format.space_before = Pt(6)  # Reduced from 12pt

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)  # Reduced from 6pt

    # Languages
    lang_para = doc.add_paragraph()
    safe_languages = [_safe_text(lang) for lang in languages_list]
    lang_para.add_run(', '.join(safe_languages))
    lang_para.paragraph_format.space_after = Pt(2)  # Reduced from 6pt


__all__ = ["render_harvard"]


