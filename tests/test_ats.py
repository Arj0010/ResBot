from backend.ats import score_ats


def test_ats_scoring_basic():
    resume = {
        "contact_info": {"full_name": "John Doe", "email": "a@b.com", "phone": "", "location": ""},
        "links": {},
        "summary": "Data scientist with 3 years experience in Python and SQL.",
        "education": [],
        "experience": [
            {"company": "ABC", "position": "Data Scientist", "location": "", "start_date": "2021", "end_date": "2023", "achievements": ["Built ML models."]}
        ],
        "projects": [],
        "certifications": [],
        "skills": {"Programming & Tools": ["Python", "SQL"], "ML & AI": ["XGBoost"], "Analytics": ["A/B Testing"]},
        "languages": ["English"]
    }
    jd = "Looking for a Data Scientist skilled in Python, SQL, and analytics."
    result = score_ats(resume, jd)
    assert 0 <= result["ats_score"] <= 100
    assert "recommendations" in result
    assert "keyword_matches" in result
    assert "missing_keywords" in result


