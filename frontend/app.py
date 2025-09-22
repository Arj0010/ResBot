import os
import json
import tempfile
from typing import Any, Dict

import gradio as gr
import requests


API_BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")


def _post_json(path: str, payload: Dict[str, Any]):
    r = requests.post(f"{API_BASE}{path}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def _post_file(path: str, file_bytes: bytes, filename: str):
    files = {"file": (filename, file_bytes)}
    r = requests.post(f"{API_BASE}{path}", files=files, timeout=60)
    r.raise_for_status()
    return r.json()


def _post_render(resume_json: Dict[str, Any]) -> str:
    r = requests.post(f"{API_BASE}/render", json=resume_json, timeout=120)
    r.raise_for_status()
    # Save the received docx stream to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".docx", delete=False)
    tmp.write(r.content)
    tmp.flush()
    tmp.close()
    return tmp.name


def _post_cover_letter(resume_json: Dict[str, Any], job_description: str, company_name: str = "", position_title: str = "") -> str:
    payload = {
        "resume_json": resume_json,
        "job_description": job_description,
        "company_name": company_name,
        "position_title": position_title
    }
    r = requests.post(f"{API_BASE}/cover-letter", json=payload, timeout=120)
    r.raise_for_status()
    # Save the received text stream to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
    tmp.write(r.content)
    tmp.flush()
    tmp.close()
    return tmp.name


def _post_interview_questions(resume_json: Dict[str, Any], job_description: str, company_name: str = "", position_title: str = "") -> str:
    payload = {
        "resume_json": resume_json,
        "job_description": job_description,
        "company_name": company_name,
        "position_title": position_title
    }
    r = requests.post(f"{API_BASE}/interview-questions", json=payload, timeout=120)
    r.raise_for_status()
    # Save the received text stream to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix=".txt", delete=False)
    tmp.write(r.content)
    tmp.flush()
    tmp.close()
    return tmp.name


def ats_bar_html(score: int, recommendations: list) -> str:
    pct = max(0, min(100, score))
    color = "#4caf50" if pct >= 75 else ("#ff9800" if pct >= 50 else "#f44336")
    # Simple HTML escaping for recommendations
    rec_html = "".join(f"<li>{rec.replace('<', '&lt;').replace('>', '&gt;')}</li>" for rec in recommendations)
    return f"""
    <div style='font-family: Calibri, sans-serif;'>
      <div style='margin-bottom:6px;'>ATS Score: <b>{pct}%</b></div>
      <div style='width:100%; background:#eee; border-radius:6px; height:16px; overflow:hidden;'>
        <div style='width:{pct}%; background:{color}; height:100%;'></div>
      </div>
      <div style='margin-top:8px;'>
        <b>Recommendations</b>
        <ul style='margin-top:4px;'>{rec_html}</ul>
      </div>
    </div>
    """


def build_app():
    with gr.Blocks(title="AI Resume Builder") as demo:
        gr.Markdown("**AI-Powered Resume Builder (Harvard Template)**")
        with gr.Row():
            with gr.Column():
                resume_file = gr.File(label="Upload Resume (PDF/DOCX/TXT/Image)")
                jd = gr.Textbox(label="Job Description", lines=10)
                cover_letter = gr.Checkbox(label="Generate Cover Letter (optional)", value=False)
                interview_q = gr.Checkbox(label="Generate Interview Questions (optional)", value=False)
                submit = gr.Button("Build Resume")
            with gr.Column():
                ats_html = gr.HTML(label="ATS Score")
                resume_json_out = gr.Textbox(label="Resume JSON (Preview)", lines=10)
                download_resume = gr.File(label="Download Harvard Resume (.docx)")
                download_cover_letter = gr.File(label="Download Cover Letter (.txt)", visible=False)
                download_interview_questions = gr.File(label="Download Interview Questions (.txt)", visible=False)

        def on_submit(file_obj, job_desc, cov, iq):
            if not file_obj or not job_desc:
                return "Please upload a resume and provide a job description.", "", None, None, None, gr.update(visible=False), gr.update(visible=False)

            try:
                # Parse
                file_bytes = open(file_obj.name, "rb").read()
                parsed = _post_file("/parse", file_bytes, os.path.basename(file_obj.name))

                # Rewrite
                payload = {"resume_json": parsed, "job_description": job_desc}
                rewrite = _post_json("/rewrite", payload)

                # Merge minimally: keep structure from parser, only replace summary and bullets when provided
                merged = parsed.copy()
                if rewrite.get("rewritten_summary"):
                    merged["summary"] = rewrite["rewritten_summary"]
                company_to_bullets = {e.get("company", ""): e.get("bullets", []) for e in rewrite.get("rewritten_experience", [])}
                for e in merged.get("experience", []):
                    e_company = e.get("company", "")
                    if e_company in company_to_bullets and company_to_bullets[e_company]:
                        e["achievements"] = company_to_bullets[e_company]

                # Skills/projects ranking (non-destructive)
                if rewrite.get("ranked_skills"):
                    merged["skills"] = rewrite["ranked_skills"]

                # Render
                docx_path = _post_render(merged)

                # ATS
                ats = _post_json("/ats", payload)
                ats_html_val = ats_bar_html(ats.get("ats_score", 0), ats.get("recommendations", []))

                # Convert to JSON string for display
                json_str = json.dumps(merged, indent=2)

                # Generate optional cover letter and interview questions
                cover_letter_path = None
                interview_questions_path = None
                cover_letter_update = gr.update(visible=False)
                interview_update = gr.update(visible=False)

                if cov:
                    try:
                        cover_letter_path = _post_cover_letter(merged, job_desc)
                        cover_letter_update = gr.update(visible=True)
                    except Exception as e:
                        print(f"Cover letter generation failed: {e}")

                if iq:
                    try:
                        interview_questions_path = _post_interview_questions(merged, job_desc)
                        interview_update = gr.update(visible=True)
                    except Exception as e:
                        print(f"Interview questions generation failed: {e}")

                return ats_html_val, json_str, docx_path, cover_letter_path, interview_questions_path, cover_letter_update, interview_update
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                return error_msg, error_msg, None, None, None, gr.update(visible=False), gr.update(visible=False)

        submit.click(on_submit, inputs=[resume_file, jd, cover_letter, interview_q], outputs=[ats_html, resume_json_out, download_resume, download_cover_letter, download_interview_questions, download_cover_letter, download_interview_questions])

    return demo


if __name__ == "__main__":
    app = build_app()
    app.launch(server_name="127.0.0.1", server_port=7871, share=True, inbrowser=False)


