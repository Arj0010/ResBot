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

        # Style configuration - Calibri 10pt as per requirements
        style = doc.styles['Normal']
        style.font.name = 'Calibri'
        style.font.size = Pt(10)  # Standard size per requirements
        # Proper line spacing for readability
        style.paragraph_format.line_spacing = 1.0
        style.paragraph_format.space_after = Pt(3)

        # Header - Name (centered) - Calibri 12pt as per requirements
        contact = resume_json.get('contact_info', {})
        name_para = doc.add_paragraph()
        name_run = name_para.add_run(_safe_text(contact.get('full_name', 'NAME')))
        name_run.font.name = 'Calibri'
        name_run.font.size = Pt(12)  # Size 12 for name as specified
        name_run.font.bold = True
        name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name_para.paragraph_format.space_after = Pt(3)

        # Contact line (centered) with hyperlinks where applicable
        contact_para = doc.add_paragraph()
        contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        links = resume_json.get('links', {})

        contact_items = []
        if contact.get('email'):
            contact_items.append(('email', contact['email'], f"mailto:{contact['email']}"))
        if contact.get('phone'):
            contact_items.append(('text', contact['phone'], None))
        if contact.get('location'):
            contact_items.append(('text', contact['location'], None))
        if links.get('LinkedIn'):
            linkedin_url = links['LinkedIn']
            display_text = linkedin_url.replace('https://', '').replace('http://', '')
            contact_items.append(('link', display_text, linkedin_url))

        # Add contact items with proper hyperlinks
        for i, (item_type, text, url) in enumerate(contact_items):
            if i > 0:
                contact_para.add_run(' | ')

            if item_type == 'link' and url:
                _add_hyperlink(contact_para, url, text)
            elif item_type == 'email' and url:
                _add_hyperlink(contact_para, url, text)
            else:
                contact_para.add_run(text)

        contact_para.paragraph_format.space_after = Pt(3)

        # Second line with additional links (GitHub, HuggingFace) if they exist
        additional_links = []
        if links.get('GitHub'):
            github_url = links['GitHub']
            display_text = github_url.replace('https://', '').replace('http://', '')
            additional_links.append((display_text, github_url))
        if links.get('HuggingFace'):
            hf_url = links['HuggingFace']
            display_text = hf_url.replace('https://', '').replace('http://', '')
            additional_links.append((display_text, hf_url))

        if additional_links:
            links_para = doc.add_paragraph()
            links_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for i, (text, url) in enumerate(additional_links):
                if i > 0:
                    links_para.add_run(' | ')
                _add_hyperlink(links_para, url, text)
            links_para.paragraph_format.space_after = Pt(6)

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
    # Section title - Calibri 10pt as per requirements
    title_para = doc.add_paragraph()
    title_run = title_para.add_run(title)
    title_run.font.name = 'Calibri'
    title_run.font.bold = True
    title_run.font.size = Pt(10)  # Size 10 for headers as specified
    title_para.paragraph_format.space_before = Pt(6)
    title_para.paragraph_format.space_after = Pt(0)

    # Divider line
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)

    # Content
    content_para = doc.add_paragraph(_safe_text(content))
    content_para.paragraph_format.space_after = Pt(3)


def _add_education_section_docx(doc, education_list):
    """Add education section to DOCX"""
    # Section title - Calibri 10pt as per requirements
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("EDUCATION")
    title_run.font.name = 'Calibri'
    title_run.font.bold = True
    title_run.font.size = Pt(10)  # Size 10 for headers as specified
    title_para.paragraph_format.space_before = Pt(6)

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)

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
    # Section title - Calibri 10pt as per requirements
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("EXPERIENCE")
    title_run.font.name = 'Calibri'
    title_run.font.bold = True
    title_run.font.size = Pt(10)  # Size 10 for headers as specified
    title_para.paragraph_format.space_before = Pt(6)

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)

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

        # Optimized bullet allocation for 1-page compliance
        exp_index = experience_list.index(exp)
        total_companies = len(experience_list)

        # Dynamic bullet allocation based on total number of companies
        if total_companies <= 3:
            bullet_limit = 4  # More space available
        elif total_companies <= 4:
            bullet_limit = 3 if exp_index <= 1 else 2  # Recent companies get more
        else:  # 5+ companies - very compact
            if exp_index <= 1:
                bullet_limit = 3  # Most recent: 3 bullets
            elif exp_index <= 3:
                bullet_limit = 2  # Mid-career: 2 bullets
            else:
                bullet_limit = 1  # Early career: 1 bullet

        for bullet in exp.get('achievements', [])[:bullet_limit]:
            bullet_para = doc.add_paragraph()
            bullet_para.add_run(f"• {_safe_text(bullet)}")
            bullet_para.paragraph_format.space_after = Pt(1)  # Compact but readable
            bullet_para.paragraph_format.left_indent = Inches(0.25)  # Proper indentation

        # Minimal space between jobs for 1-page compliance
        if exp_index < len(experience_list) - 1:  # Don't add space after last job
            doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _add_projects_section_docx(doc, projects_list):
    """Add projects section to DOCX"""
    # Section title - Calibri 10pt as per requirements
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("PROJECTS")
    title_run.font.name = 'Calibri'
    title_run.font.bold = True
    title_run.font.size = Pt(10)  # Size 10 for headers as specified
    title_para.paragraph_format.space_before = Pt(6)

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)

    # Project entries
    for project in projects_list:
        # Project title (bold)
        title_para = doc.add_paragraph()
        title_run = title_para.add_run(_safe_text(project.get('title', '')))
        title_run.font.bold = True

        # Optimized bullet allocation for projects based on 1-page constraint
        project_index = projects_list.index(project)
        total_projects = len(projects_list)

        # Dynamic project bullet allocation
        if total_projects == 1:
            bullet_limit = 3  # Single project can have more detail
        elif total_projects == 2:
            bullet_limit = 2  # Two projects get moderate detail
        else:
            bullet_limit = 1  # 3+ projects need to be very compact

        for bullet in project.get('bullets', [])[:bullet_limit]:
            bullet_para = doc.add_paragraph()
            bullet_para.add_run(f"• {_safe_text(bullet)}")
            bullet_para.paragraph_format.space_after = Pt(1)
            bullet_para.paragraph_format.left_indent = Inches(0.25)

        # Minimal space between projects for 1-page compliance
        if project_index < len(projects_list) - 1:  # Don't add space after last project
            doc.add_paragraph().paragraph_format.space_after = Pt(2)


def _add_certificates_section_docx(doc, certificates_list):
    """Add certificates section to DOCX"""
    # Section title - Calibri 10pt as per requirements
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("CERTIFICATES")
    title_run.font.name = 'Calibri'
    title_run.font.bold = True
    title_run.font.size = Pt(10)  # Size 10 for headers as specified
    title_para.paragraph_format.space_before = Pt(6)

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)

    # Certificate entries - compact format with limited count for 1-page compliance
    max_certs = min(len(certificates_list), 6)  # Limit certificates to maintain 1-page
    for cert in certificates_list[:max_certs]:
        cert_para = doc.add_paragraph()
        cert_text = _safe_text(cert) if isinstance(cert, str) else _safe_text(cert.get('name', ''))
        cert_para.add_run(f"• {cert_text}")
        cert_para.paragraph_format.space_after = Pt(0.5)  # Very compact
        cert_para.paragraph_format.left_indent = Inches(0.25)


def _add_skills_section_docx(doc, skills_dict):
    """Add skills section to DOCX"""
    # Section title - Calibri 10pt as per requirements
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("SKILLS")
    title_run.font.name = 'Calibri'
    title_run.font.bold = True
    title_run.font.size = Pt(10)  # Size 10 for headers as specified
    title_para.paragraph_format.space_before = Pt(6)

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)

    # Skill categories - format like reference resume
    categories = {
        'Programming & Tools': 'Programming & Tools',
        'ML & AI': 'Machine Learning & AI',
        'Analytics': 'Data Analytics & Reporting'
    }

    for key, title in categories.items():
        if skills_dict.get(key):
            # Category title (bold) with skills in same line
            skills_para = doc.add_paragraph()
            title_run = skills_para.add_run(f"{title} ")
            title_run.font.bold = True

            # Skills in comma-separated format (not parentheses)
            skills_text = ', '.join([_safe_text(skill) for skill in skills_dict[key]])
            skills_para.add_run(f"({skills_text})")
            skills_para.paragraph_format.space_after = Pt(3)


def _add_languages_section_docx(doc, languages_list):
    """Add languages section to DOCX"""
    if not languages_list:
        return

    # Section title - Calibri 10pt as per requirements
    title_para = doc.add_paragraph()
    title_run = title_para.add_run("LANGUAGES")
    title_run.font.name = 'Calibri'
    title_run.font.bold = True
    title_run.font.size = Pt(10)  # Size 10 for headers as specified
    title_para.paragraph_format.space_before = Pt(6)

    # Divider
    divider_para = doc.add_paragraph()
    divider_run = divider_para.add_run("_" * 87)
    divider_para.paragraph_format.space_after = Pt(3)

    # Languages
    lang_para = doc.add_paragraph()
    safe_languages = [_safe_text(lang) for lang in languages_list]
    lang_para.add_run(', '.join(safe_languages))
    lang_para.paragraph_format.space_after = Pt(3)


__all__ = ["render_harvard"]


