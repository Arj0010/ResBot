import os
from backend.parser import parse_resume


def test_parse_returns_all_sections(tmp_path):
    p = tmp_path / "resume.txt"
    p.write_text("John Doe\njohn@example.com\nEducation\nExperience\n", encoding="utf-8")
    data = parse_resume(str(p))
    assert "contact_info" in data
    assert "links" in data
    assert "summary" in data
    assert "education" in data
    assert "experience" in data
    assert "projects" in data
    assert "certifications" in data
    assert "skills" in data
    assert "languages" in data


