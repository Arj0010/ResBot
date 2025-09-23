from backend.renderer import render_harvard

resume_json = {
    "contact_info": {
        "full_name": "Arjun Vavullipathy",
        "email": "arjun@example.com",
        "phone": "9876543210",
        "location": "Bangalore"
    },
    "links": {
        "LinkedIn": "linkedin.com/in/arjunv",
        "GitHub": "github.com/Arjun0010",
        "HuggingFace": "huggingface.co/Arjun0000v"
    },
    "summary": "Highly motivated AI Engineer proficient in Python and NLP.",
    "education": [
        {"institution": "St Joseph’s University", "degree": "BCA", "field": "Data Analytics", "location": "Bangalore", "graduation_date": "2025", "gpa": "7.7"}
    ],
    "experience": [
        {"company": "Oryzed", "position": "AI Intern", "location": "Bangalore", "start_date": "2025-07", "end_date": "Present",
         "achievements": ["Built chatbot using LLaMA 3.1", "Developed NLP pipelines"]}
    ],
    "projects": [
        {"title": "Suicide Prediction Dashboard", "description": "ML model with PCA and Power BI", "technologies": ["Python", "PCA"], "bullets": ["Achieved 88% accuracy", "Integrated dashboard with Power BI"]}
    ],
    "certifications": ["Supervised Machine Learning – DeepLearning.AI"],
    "skills": {
        "Technical": ["Python", "NLP", "SQL"],
        "Non-Technical": ["Communication", "Teamwork"]
    },
    "languages": ["English", "Hindi"]
}

render_harvard(resume_json, "test_resume.docx", "AI Engineer at TechCorp")
print("✅ DOCX generated: test_resume.docx")
