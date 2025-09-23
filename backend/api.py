import io
import os
import tempfile
from typing import Dict, Any

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.parser import extract_text
from .llm import rewrite_resume, generate_cover_letter, generate_interview_questions,llm_parse_resume
from .renderer import render_harvard
from .html_renderer import render_html_resume
from .ats import score_ats


app = FastAPI(title="Resume Builder API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class RewriteRequest(BaseModel):
    resume_json: dict
    job_description: str


class AtsRequest(BaseModel):
    resume_json: dict
    job_description: str


class CoverLetterRequest(BaseModel):
    resume_json: dict
    job_description: str
    company_name: str = ""
    position_title: str = ""


class InterviewQuestionsRequest(BaseModel):
    resume_json: dict
    job_description: str
    company_name: str = ""
    position_title: str = ""


@app.post("/parse")
async def parse_resume_api(file: UploadFile = File(...)):
    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        raw_text = extract_text(tmp_path)
        parsed = llm_parse_resume(raw_text)
        return JSONResponse(content=parsed)
    finally:
        os.unlink(tmp_path)

@app.post("/rewrite")
async def rewrite_endpoint(body: RewriteRequest):
    payload = rewrite_resume(body.resume_json, body.job_description)
    return JSONResponse(content=payload)


@app.post("/render")
async def render_endpoint(request_data: Dict[str, Any]):
    # Check if this is already merged data or needs LLM optimization
    resume_json = request_data.copy()

    # If we have both original data and rewrite instructions, merge them
    if "rewritten_experience" in request_data or "rewritten_summary" in request_data:
        # This is LLM-optimized data, use it directly
        pass
    elif "job_description" in request_data:
        # Need to optimize with LLM first
        llm_output = rewrite_resume(resume_json, request_data["job_description"])

        # Merge LLM optimizations into the original data
        if llm_output.get("rewritten_summary"):
            resume_json["summary"] = llm_output["rewritten_summary"]

        # Update experience achievements with LLM-optimized bullets
        if llm_output.get("rewritten_experience"):
            company_to_bullets = {
                exp.get("company", ""): exp.get("bullets", [])
                for exp in llm_output["rewritten_experience"]
            }

            for exp in resume_json.get("experience", []):
                company = exp.get("company", "")
                if company in company_to_bullets and company_to_bullets[company]:
                    exp["achievements"] = company_to_bullets[company]

        # Update skills ranking if available
        if llm_output.get("ranked_skills"):
            resume_json["skills"] = llm_output["ranked_skills"]

        # Update project ranking if available
        if llm_output.get("ranked_projects"):
            # Reorder projects based on LLM ranking
            original_projects = resume_json.get("projects", [])
            project_title_to_obj = {proj.get("title", ""): proj for proj in original_projects}
            ranked_projects = []
            for title in llm_output["ranked_projects"]:
                if title in project_title_to_obj:
                    ranked_projects.append(project_title_to_obj[title])
            # Add any projects not in ranking
            for proj in original_projects:
                if proj not in ranked_projects:
                    ranked_projects.append(proj)
            resume_json["projects"] = ranked_projects

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_out:
        output_path = tmp_out.name
    template_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates", "harvard.json")
    render_harvard(resume_json, output_path, template_path)
    docx_bytes = open(output_path, "rb").read()
    os.unlink(output_path)
    return StreamingResponse(io.BytesIO(docx_bytes), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=resume.docx"})


@app.post("/ats")
async def ats_endpoint(body: AtsRequest):
    result = score_ats(body.resume_json, body.job_description)
    return JSONResponse(content=result)


@app.post("/cover-letter")
async def cover_letter_endpoint(body: CoverLetterRequest):
    cover_letter_text = generate_cover_letter(
        body.resume_json,
        body.job_description,
        body.company_name,
        body.position_title
    )

    # Create a simple text file for download
    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as tmp_out:
        tmp_out.write(cover_letter_text)
        output_path = tmp_out.name

    text_bytes = open(output_path, "rb").read()
    os.unlink(output_path)
    return StreamingResponse(
        io.BytesIO(text_bytes),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=cover_letter.txt"}
    )


@app.post("/interview-questions")
async def interview_questions_endpoint(body: InterviewQuestionsRequest):
    questions_text = generate_interview_questions(
        body.resume_json,
        body.job_description,
        body.company_name,
        body.position_title
    )

    # Create a simple text file for download
    with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as tmp_out:
        tmp_out.write(questions_text)
        output_path = tmp_out.name

    text_bytes = open(output_path, "rb").read()
    os.unlink(output_path)
    return StreamingResponse(
        io.BytesIO(text_bytes),
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=interview_questions.txt"}
    )


@app.post("/render-html")
async def render_html(request: dict):
    """Generate HTML resume with strict formatting rules"""
    try:
        html_content = render_html_resume(request)

        # Create HTML file for download
        with tempfile.NamedTemporaryFile(mode='w', suffix=".html", delete=False, encoding='utf-8') as tmp_out:
            tmp_out.write(html_content)
            output_path = tmp_out.name

        html_bytes = open(output_path, "rb").read()
        os.unlink(output_path)

        return StreamingResponse(
            io.BytesIO(html_bytes),
            media_type="text/html",
            headers={"Content-Disposition": "attachment; filename=resume.html"}
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/")
async def root():
    return {"status": "ok"}


