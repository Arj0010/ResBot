import json
from pydoc import doc
import re
import os
from typing import Dict, Any, List
from datetime import datetime

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

def _ensure_url(url: str) -> str:
    if not url:
        return url
    u = url.strip()
    if u.startswith("mailto:") or u.startswith("http://") or u.startswith("https://"):
        return u
    if u.startswith("www."):
        return "https://" + u
    return "https://" + u

def _add_hyperlink(paragraph, url, text):
    """Add a clickable hyperlink to a paragraph."""
    url = _ensure_url(url)
    part = paragraph.part
    r_id = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)

    hyperlink = OxmlElement('w:hyperlink')
    hyperlink.set(qn('r:id'), r_id)

    new_run = OxmlElement('w:r')
    rPr = OxmlElement('w:rPr')

    # underline + blue color
    u = OxmlElement('w:u'); u.set(qn('w:val'), 'single'); rPr.append(u)
    color = OxmlElement('w:color'); color.set(qn('w:val'), "0000FF"); rPr.append(color)

    new_run.append(rPr)
    t = OxmlElement('w:t'); t.text = text
    new_run.append(t)
    hyperlink.append(new_run)
    paragraph._element.append(hyperlink)
    return hyperlink

def _add_divider(doc):
    p = doc.add_paragraph()
    p_par = p._element
    pPr = p_par.get_or_add_pPr()
    p_borders = OxmlElement('w:pBdr')
    bottom = OxmlElement('w:bottom')
    bottom.set(qn('w:val'), 'single')
    bottom.set(qn('w:sz'), '6')
    bottom.set(qn('w:space'), '1')
    bottom.set(qn('w:color'), '000000')
    p_borders.append(bottom)
    pPr.append(p_borders)
    return p


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



def render_harvard(resume_json, output_path: str, job_title: str = ""):
    doc = Document()

    style = doc.styles['Normal']
    style.font.name = 'Times New Roman'
    style.font.size = Pt(11)

    # tighten paragraph spacing globally for compact Harvard look
    for pstyle in doc.styles:
        try:
            pstyle.paragraph_format.space_after = Pt(2)
        except Exception:
            pass
    # --- Header: centered name + single contact line with clickable links ---
    name = resume_json.get("contact_info", {}).get("full_name", "")
    if name:
        p = doc.add_paragraph()
        p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        r = p.add_run(name)
        r.bold = True
        r.font.size = Pt(16)
        p.paragraph_format.space_after = Pt(4)

    # Build contact pieces
    ci = resume_json.get("contact_info", {})
    links = resume_json.get("links", {}) or {}

    # create a centered paragraph and add text runs + hyperlinks
    cp = doc.add_paragraph()
    cp.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
    parts = []
    if ci.get("location"):
        parts.append(("text", ci["location"]))
    if ci.get("email"):
        parts.append(("text", ci["email"]))
    if ci.get("phone"):
        parts.append(("text", ci["phone"]))

    # Ordered preferred links
    preferred = ["LinkedIn", "GitHub", "HuggingFace"]
    link_items = []
    for key in preferred:
        if links.get(key):
            link_items.append((key, links[key]))
    # any other links
    for k, v in links.items():
        if k not in preferred and v:
            link_items.append((k, v))

    # Write items to paragraph
    first = True
    for t in parts:
        if not first:
            cp.add_run(" • ")
        cp.add_run(t[1] if isinstance(t, tuple) else t)
        first = False

    for idx, (label, url) in enumerate(link_items):
        if not first:
            cp.add_run(" • ")
        _add_hyperlink(cp, url, label)
        first = False

    cp.paragraph_format.space_after = Pt(6)
    _add_divider(doc)

    # === Summary ===
    if resume_json.get("summary"):
        _add_section_title(doc, "SUMMARY")
        doc.add_paragraph(resume_json["summary"])
        _add_divider(doc)

    # === Education ===
    if resume_json.get("education"):
        _add_section_title(doc, "EDUCATION")
        for edu in resume_json["education"]:
            table = doc.add_table(rows=1, cols=2)
            table.allow_autofit = True
            left_cell, right_cell = table.rows[0].cells

            # Left cell: Institution + location
            p = left_cell.paragraphs[0]
            run = p.add_run(edu.get("institution", ""))
            run.bold = True
            if edu.get("location"):
                p.add_run(f" — {edu['location']}")

            # Right cell: Graduation date
            if edu.get("graduation_date"):
                rp = right_cell.paragraphs[0]
                rp.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
                rp.add_run(edu["graduation_date"])

            # Next line: Degree + field + GPA
            degree_line = f"{edu.get('degree','')} in {edu.get('field','')}"
            if edu.get("gpa"):
                degree_line += f", GPA: {edu['gpa']}"
            left_cell.add_paragraph(degree_line)

        doc.add_paragraph()
        _add_divider(doc)

    # === Experience (table layout so dates align on right) ===
    if resume_json.get("experience"):
        _add_section_title(doc, "EXPERIENCE")
        for exp in resume_json["experience"]:
            table = doc.add_table(rows=1, cols=2)
            table.allow_autofit = True
            left_cell, right_cell = table.rows[0].cells

            # Left: company (bold) + position (italic) + bullets
            left_para = left_cell.paragraphs[0]
            left_run = left_para.add_run(_safe_text(exp.get("company", "")))
            left_run.bold = True

            # position on next line
            if exp.get("position"):
                pos_p = left_cell.add_paragraph()
                pos_run = pos_p.add_run(_safe_text(exp.get("position")))
                pos_run.italic = True

            # bullets
            for b in exp.get("achievements", []):
                bull_p = left_cell.add_paragraph()
                bull_p.add_run(f"• {_safe_text(b)}")
                bull_p.paragraph_format.space_after = Pt(1)

            # Right: dates / location (top-right)
            right_para = right_cell.paragraphs[0]
            date_text = ""
            if exp.get("start_date") or exp.get("end_date"):
                date_text = f"{exp.get('start_date','')} – {exp.get('end_date','')}"
            if exp.get("location"):
                date_text = (date_text + " | " if date_text else "") + exp.get("location")
            right_para.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT
            right_para.add_run(date_text)

        # small space after section
        doc.add_paragraph()


    # === Projects ===
    if resume_json.get("projects"):
        _add_section_title(doc, "PROJECTS")
        for proj in resume_json["projects"]:
            p = doc.add_paragraph()
            run = p.add_run(proj.get("title", ""))
            run.bold = True
            if proj.get("technologies"):
                p.add_run(f" — {', '.join(proj['technologies'])}")

            for b in proj.get("bullets", []):
                doc.add_paragraph(f"• {b}")
        _add_divider(doc)

    # === Skills & Interests ===
    skills = resume_json.get("skills", {})
    langs = resume_json.get("languages", [])
    certs = resume_json.get("certifications", [])

    if skills or langs or certs:
        _add_section_title(doc, "SKILLS & INTERESTS")

        if skills:
            for cat, items in skills.items():
                doc.add_paragraph(f"{cat}: {', '.join(items)}")

        if langs:
            doc.add_paragraph("Languages: " + ", ".join(langs))

        if certs:
            doc.add_paragraph("Certifications: " + ", ".join(certs))

    # Save DOCX
    doc.save(output_path)

def _add_section_title(doc, title: str):
    p = doc.add_paragraph()
    run = p.add_run(title.upper())
    run.bold = True
    p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT

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
    _add_divider(doc)
    
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
    _add_divider(doc)

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
    _add_divider(doc)

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
    _add_divider(doc)
 
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
    _add_divider(doc)

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
    _add_divider(doc)

    # Dynamic skill categories - process all categories in skills_dict
    for category, skills in skills_dict.items():
        if skills:  # Only show categories that have skills
            # Category title (bold) with skills in same line
            skills_para = doc.add_paragraph()
            title_run = skills_para.add_run(f"{category} ")
            title_run.font.bold = True

            # Skills in comma-separated format in parentheses
            skills_text = ', '.join([_safe_text(skill) for skill in skills])
            skills_para.add_run(f"({skills_text})")
            skills_para.paragraph_format.space_after = Pt(3)


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
    _add_divider(doc)

    # Languages
    lang_para = doc.add_paragraph()
    safe_languages = [_safe_text(lang) for lang in languages_list]
    lang_para.add_run(', '.join(safe_languages))
    lang_para.paragraph_format.space_after = Pt(2)  # Reduced from 6pt


__all__ = ["render_harvard"]


