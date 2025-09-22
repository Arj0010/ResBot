import re
from typing import Dict, Any, List


def _safe_text(text: str) -> str:
    """Ensure text is safe for HTML by escaping special characters."""
    if not text:
        return ""

    # Basic HTML escaping
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#x27;')

    # Clean up whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()

    return text


def render_html_resume(resume_json: Dict[str, Any]) -> str:
    """Generate clean HTML resume with strict formatting rules"""

    html_parts = []

    # Start HTML with responsive wrapper
    html_parts.append('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resume</title>
    <style>
        body {
            font-family: 'Times New Roman', serif;
            line-height: 1.4;
            margin: 0;
            padding: 20px;
            color: #333;
        }
        .container {
            max-width: 800px;
            margin: auto;
            background: white;
            padding: 30px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        .name {
            font-size: 24px;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .contact {
            font-size: 14px;
            color: #666;
            margin-bottom: 20px;
        }
        .section-title {
            font-size: 16px;
            font-weight: bold;
            margin-top: 20px;
            margin-bottom: 10px;
            text-transform: uppercase;
        }
        .divider {
            width: 100%;
            border: 1px solid #ccc;
            margin: 10px 0;
        }
        .experience-item {
            margin-bottom: 15px;
        }
        .job-header {
            display: flex;
            justify-content: space-between;
            font-weight: bold;
            margin-bottom: 5px;
        }
        .achievements {
            margin-left: 20px;
        }
        .achievement {
            margin-bottom: 3px;
        }
        .skills-category {
            margin-bottom: 8px;
        }
        .skills-category strong {
            display: inline-block;
            min-width: 100px;
        }
        a {
            color: #0066cc;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        @media (max-width: 600px) {
            .job-header {
                flex-direction: column;
            }
            .container {
                padding: 15px;
            }
        }
    </style>
</head>
<body>
    <div class="container">''')

    # Header - Name and Contact
    contact = resume_json.get('contact_info', {})
    links = resume_json.get('links', {})

    html_parts.append('<div class="header">')

    # Name
    name = contact.get('full_name', '')
    if name:
        html_parts.append(f'<div class="name">{_safe_text(name)}</div>')

    # Contact info
    contact_parts = []
    if contact.get('email'):
        email = contact['email']
        contact_parts.append(f'<a href="mailto:{email}" target="_blank">{_safe_text(email)}</a>')

    if contact.get('phone'):
        contact_parts.append(_safe_text(contact['phone']))

    if contact.get('location'):
        contact_parts.append(_safe_text(contact['location']))

    # Add clickable links
    for link_name, url in links.items():
        if url and url.strip():
            contact_parts.append(f'<a href="{url}" target="_blank">{_safe_text(link_name)}</a>')

    if contact_parts:
        html_parts.append(f'<div class="contact">{" • ".join(contact_parts)}</div>')

    html_parts.append('</div>')

    # Summary/Career Objective (only if provided)
    summary = resume_json.get('summary', '')
    if summary and summary.strip():
        html_parts.append('<div class="section-title">Career Objective</div>')
        html_parts.append('<hr class="divider">')
        html_parts.append(f'<p>{_safe_text(summary)}</p>')

    # Skills (only if provided and structured)
    skills = resume_json.get('skills', {})
    if skills and any(skills.values()):
        html_parts.append('<div class="section-title">Skills</div>')
        html_parts.append('<hr class="divider">')

        # Technical skills
        technical_skills = []
        for cat in ['Programming & Tools', 'ML & AI', 'Analytics']:
            if skills.get(cat):
                technical_skills.extend(skills[cat])

        if technical_skills:
            html_parts.append('<div class="skills-category">')
            html_parts.append('<strong>Technical:</strong> ')
            html_parts.append(', '.join([_safe_text(skill) for skill in technical_skills]))
            html_parts.append('</div>')

        # Tools (if separate category exists)
        if skills.get('Tools'):
            html_parts.append('<div class="skills-category">')
            html_parts.append('<strong>Tools:</strong> ')
            html_parts.append(', '.join([_safe_text(tool) for tool in skills['Tools']]))
            html_parts.append('</div>')

        # Soft skills (if exists)
        if skills.get('Soft Skills'):
            html_parts.append('<div class="skills-category">')
            html_parts.append('<strong>Soft Skills:</strong> ')
            html_parts.append(', '.join([_safe_text(skill) for skill in skills['Soft Skills']]))
            html_parts.append('</div>')

    # Experience (only if provided) - DO NOT REMOVE ANY EXPERIENCE
    experience = resume_json.get('experience', [])
    if experience:
        html_parts.append('<div class="section-title">Experience</div>')
        html_parts.append('<hr class="divider">')

        for exp in experience:
            company = _safe_text(exp.get('company', ''))
            position = _safe_text(exp.get('position', ''))
            location = _safe_text(exp.get('location', ''))
            start_date = _safe_text(exp.get('start_date', ''))
            end_date = _safe_text(exp.get('end_date', 'Present'))

            html_parts.append('<div class="experience-item">')

            # Job header with company, role, and dates
            html_parts.append('<div class="job-header">')
            html_parts.append(f'<div>{position}, {company}</div>')

            date_location = f'{start_date} – {end_date}'
            if location:
                date_location += f' | {location}'
            html_parts.append(f'<div>{date_location}</div>')
            html_parts.append('</div>')

            # Achievements
            achievements = exp.get('achievements', [])
            if achievements:
                html_parts.append('<div class="achievements">')
                for achievement in achievements:
                    html_parts.append(f'<div class="achievement">• {_safe_text(achievement)}</div>')
                html_parts.append('</div>')

            html_parts.append('</div>')

    # Education (only if provided)
    education = resume_json.get('education', [])
    if education:
        html_parts.append('<div class="section-title">Education</div>')
        html_parts.append('<hr class="divider">')

        for edu in education:
            institution = _safe_text(edu.get('institution', ''))
            degree = _safe_text(edu.get('degree', ''))
            field = _safe_text(edu.get('field', ''))
            location = _safe_text(edu.get('location', ''))
            graduation_date = _safe_text(edu.get('graduation_date', ''))
            gpa = _safe_text(edu.get('gpa', ''))

            html_parts.append('<div class="experience-item">')
            html_parts.append('<div class="job-header">')

            degree_info = degree
            if field:
                degree_info += f' in {field}'
            if gpa:
                degree_info += f' – {gpa}'

            html_parts.append(f'<div><strong>{institution}</strong></div>')

            date_location = graduation_date
            if location:
                date_location += f' | {location}' if date_location else location
            html_parts.append(f'<div>{date_location}</div>')
            html_parts.append('</div>')

            if degree_info:
                html_parts.append(f'<div>{degree_info}</div>')

            html_parts.append('</div>')

    # Certificates (only if provided)
    certificates = resume_json.get('certifications', [])
    if certificates:
        html_parts.append('<div class="section-title">Certificates</div>')
        html_parts.append('<hr class="divider">')

        for cert in certificates:
            if isinstance(cert, str):
                html_parts.append(f'<div class="achievement">• {_safe_text(cert)}</div>')
            elif isinstance(cert, dict):
                cert_name = _safe_text(cert.get('name', ''))
                issuer = _safe_text(cert.get('issuer', ''))
                year = _safe_text(cert.get('year', ''))

                cert_text = cert_name
                if issuer:
                    cert_text += f' — {issuer}'
                if year:
                    cert_text += f' ({year})'

                html_parts.append(f'<div class="achievement">• {cert_text}</div>')

    # Projects (only if provided)
    projects = resume_json.get('projects', [])
    if projects:
        html_parts.append('<div class="section-title">Projects</div>')
        html_parts.append('<hr class="divider">')

        for project in projects:
            title = _safe_text(project.get('title', ''))
            description = _safe_text(project.get('description', ''))

            html_parts.append('<div class="experience-item">')
            html_parts.append(f'<div class="job-header"><div><strong>{title}</strong></div></div>')

            if description:
                html_parts.append(f'<div>{description}</div>')

            bullets = project.get('bullets', [])
            if bullets:
                html_parts.append('<div class="achievements">')
                for bullet in bullets:
                    html_parts.append(f'<div class="achievement">• {_safe_text(bullet)}</div>')
                html_parts.append('</div>')

            html_parts.append('</div>')

    # Languages (only if provided)
    languages = resume_json.get('languages', [])
    if languages:
        html_parts.append('<div class="section-title">Languages</div>')
        html_parts.append('<hr class="divider">')
        language_list = ', '.join([_safe_text(lang) for lang in languages])
        html_parts.append(f'<p>{language_list}</p>')

    # Close HTML
    html_parts.append('</div></body></html>')

    return '\n'.join(html_parts)


__all__ = ["render_html_resume"]