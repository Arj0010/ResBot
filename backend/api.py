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
    # Get the tailored resume with full schema
    tailored_resume = rewrite_resume(body.resume_json, body.job_description)
    return JSONResponse(content=tailored_resume)


@app.post("/render")
async def render_endpoint(resume_json: Dict[str, Any]):
    # Render the resume JSON directly (should be already optimized from /rewrite)
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




@app.get("/")
async def root():
    return {"status": "ok"}


