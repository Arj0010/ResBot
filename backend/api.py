import io
import os
import tempfile
from typing import Dict, Any

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from backend.parser import extract_text, fallback_extract
from .llm import rewrite_resume, generate_cover_letter, generate_interview_questions, llm_parse_resume
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
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            contents = await file.read()
            tmp.write(contents)
            tmp_path = tmp.name

        raw_text = extract_text(tmp_path)
        parsed = llm_parse_resume(raw_text)
        parsed = fallback_extract(raw_text, parsed)
        return JSONResponse(content=parsed)
    except Exception as e:
        print(f"Error in /parse: {e}")
        return JSONResponse(content={"error": f"Failed to parse resume: {str(e)}"}, status_code=500)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@app.post("/rewrite")
async def rewrite_endpoint(body: RewriteRequest):
    try:
        print(f"DEBUG API: Received rewrite request")
        print(f"DEBUG API: Input keys: {list(body.resume_json.keys())}")
        tailored_resume = rewrite_resume(body.resume_json, body.job_description)
        print(f"DEBUG API: Output keys: {list(tailored_resume.keys())}")
        return JSONResponse(content=tailored_resume)
    except Exception as e:
        print(f"Error in /rewrite: {e}")
        return JSONResponse(content={"error": f"Failed to rewrite resume: {str(e)}"})


@app.post("/render")
async def render_endpoint(resume_json: Dict[str, Any]):
    output_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp_out:
            output_path = tmp_out.name
        render_harvard(resume_json, output_path)
        docx_bytes = open(output_path, "rb").read()
        return StreamingResponse(io.BytesIO(docx_bytes), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={"Content-Disposition": "attachment; filename=resume.docx"})
    except Exception as e:
        print(f"Error in /render: {e}")
        return JSONResponse(content={"error": f"Failed to render resume: {str(e)}"})
    finally:
        if output_path and os.path.exists(output_path):
            os.unlink(output_path)


@app.post("/ats")
async def ats_endpoint(body: AtsRequest):
    try:
        result = score_ats(body.resume_json, body.job_description)
        return JSONResponse(content=result)
    except Exception as e:
        print(f"Error in /ats: {e}")
        return JSONResponse(content={"error": f"Failed to calculate ATS score: {str(e)}"})


@app.post("/cover-letter")
async def cover_letter_endpoint(body: CoverLetterRequest):
    output_path = None
    try:
        cover_letter_text = generate_cover_letter(
            body.resume_json,
            body.job_description,
            body.company_name,
            body.position_title
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as tmp_out:
            tmp_out.write(cover_letter_text)
            output_path = tmp_out.name

        text_bytes = open(output_path, "rb").read()
        return StreamingResponse(
            io.BytesIO(text_bytes),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=cover_letter.txt"}
        )
    except Exception as e:
        print(f"Error in /cover-letter: {e}")
        return JSONResponse(content={"error": f"Failed to generate cover letter: {str(e)}"})
    finally:
        if output_path and os.path.exists(output_path):
            os.unlink(output_path)


@app.post("/interview-questions")
async def interview_questions_endpoint(body: InterviewQuestionsRequest):
    output_path = None
    try:
        questions_text = generate_interview_questions(
            body.resume_json,
            body.job_description,
            body.company_name,
            body.position_title
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix=".txt", delete=False, encoding='utf-8') as tmp_out:
            tmp_out.write(questions_text)
            output_path = tmp_out.name

        text_bytes = open(output_path, "rb").read()
        return StreamingResponse(
            io.BytesIO(text_bytes),
            media_type="text/plain",
            headers={"Content-Disposition": "attachment; filename=interview_questions.txt"}
        )
    except Exception as e:
        print(f"Error in /interview-questions: {e}")
        return JSONResponse(content={"error": f"Failed to generate interview questions: {str(e)}"})
    finally:
        if output_path and os.path.exists(output_path):
            os.unlink(output_path)




@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/debug-test")
async def debug_test():
    print("DEBUG TEST ENDPOINT CALLED!")
    return {"debug": "test endpoint works"}


