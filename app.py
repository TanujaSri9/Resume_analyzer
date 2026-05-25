from flask import Flask, Response, render_template, request, url_for
from google import genai
from google.genai import errors as genai_errors
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
import pdfplumber
import os
import json

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).with_name(".env"), override=True)
except ImportError:
    pass

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
SITE_URL = os.getenv("SITE_URL", "").rstrip("/")
HISTORY_FILE = Path(__file__).with_name("data") / "history.json"
TARGET_ROLES = [
    "General",
    "Software Developer",
    "Data Analyst",
    "Cybersecurity Analyst",
    "UI/UX Designer",
    "AI/ML Engineer",
    "Cloud Engineer",
    "Fresher / Internship",
]
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def load_history():
    if not HISTORY_FILE.exists():
        return []

    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as history_file:
            history = json.load(history_file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(history, list):
        return []

    return history


def save_history_record(filename, target_role, job_description, analysis):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "target_role": target_role,
        "has_job_description": bool(job_description),
        "job_description_preview": job_description[:220],
        "analysis": analysis,
    }

    history = load_history()
    history.insert(0, record)
    history = history[:25]

    with HISTORY_FILE.open("w", encoding="utf-8") as history_file:
        json.dump(history, history_file, indent=2)

    return record


def get_history_record(record_id):
    for record in load_history():
        if record.get("id") == record_id:
            return record

    return None


def analyze_resume_with_gemini(resume_text, target_role, job_description):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing in .env file."
        )

    client = genai.Client(api_key=api_key)

    schema = {
        "type": "object",
        "properties": {
            "ats_score": {"type": "integer"},
            "job_match_score": {"type": "integer"},
            "role_fit_score": {"type": "integer"},
            "target_role": {"type": "string"},
            "summary": {"type": "string"},
            "job_description_alignment": {"type": "string"},
            "strengths": {"type": "array", "items": {"type": "string"}},
            "weaknesses": {"type": "array", "items": {"type": "string"}},
            "missing_skills": {"type": "array", "items": {"type": "string"}},
            "matched_keywords": {"type": "array", "items": {"type": "string"}},
            "missing_job_keywords": {"type": "array", "items": {"type": "string"}},
            "role_based_recommendations": {"type": "array", "items": {"type": "string"}},
            "improvement_suggestions": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "ats_score",
            "job_match_score",
            "role_fit_score",
            "target_role",
            "summary",
            "job_description_alignment",
            "strengths",
            "weaknesses",
            "missing_skills",
            "matched_keywords",
            "missing_job_keywords",
            "role_based_recommendations",
            "improvement_suggestions",
        ],
    }

    job_description_context = (
        job_description[:8000]
        if job_description
        else "No job description was provided. Estimate job match using the selected target role and general hiring expectations."
    )

    prompt = f"""
You are an expert ATS resume reviewer.

Analyze this resume for the selected target role and the job description if provided.

Score the resume from 0 to 100 based on ATS readability, keyword strength,
clarity, formatting, measurable impact, and skills alignment.

Also score:
- job_match_score from 0 to 100 based on alignment with the job description. If no job description is provided, use general expectations for the selected target role.
- role_fit_score from 0 to 100 based on how strongly the resume fits the selected target role.

Return concise, practical feedback. Keep arrays to 3 to 6 items each.

Return only JSON that matches this schema:
- ats_score: integer from 0 to 100
- job_match_score: integer from 0 to 100
- role_fit_score: integer from 0 to 100
- target_role: string
- summary: string
- job_description_alignment: string
- strengths: array of strings
- weaknesses: array of strings
- missing_skills: array of strings
- matched_keywords: array of strings
- missing_job_keywords: array of strings
- role_based_recommendations: array of strings
- improvement_suggestions: array of strings

Target role:
{target_role}

Job description:
{job_description_context}

Resume:
{resume_text[:15000]}
"""

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": schema,
        },
    )

    return json.loads(response.text)


@app.route("/")
def home():
    return render_template("index.html", target_roles=TARGET_ROLES)


@app.route("/robots.txt")
def robots_txt():
    sitemap_url = f"{SITE_URL}/sitemap.xml" if SITE_URL else url_for("sitemap_xml", _external=True)
    robots = f"""User-agent: *
Allow: /
Disallow: /analyze
Disallow: /history

Sitemap: {sitemap_url}
"""
    return Response(robots, mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    base_url = SITE_URL or request.url_root.rstrip("/")
    updated_at = datetime.now(timezone.utc).date().isoformat()
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>{base_url}/</loc>
        <lastmod>{updated_at}</lastmod>
        <changefreq>weekly</changefreq>
        <priority>1.0</priority>
    </url>
</urlset>
"""
    return Response(sitemap, mimetype="application/xml")


@app.errorhandler(RequestEntityTooLarge)
def file_too_large(error):
    return render_template("result.html", error="The PDF is too large. Please upload a file under 8 MB."), 413


@app.route("/analyze", methods=["POST"])
def analyze_resume():

    if "resume" not in request.files:
        return render_template("result.html", error="No file was uploaded.")

    file = request.files["resume"]

    if file.filename == "":
        return render_template("result.html", error="No file was selected.")

    if not allowed_file(file.filename):
        return render_template("result.html", error="Please upload a PDF resume.")

    target_role = request.form.get("target_role", "General").strip()
    if target_role not in TARGET_ROLES:
        target_role = "General"

    job_description = request.form.get("job_description", "").strip()

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    extracted_text = ""

    try:
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                extracted_text += page.extract_text() or ""
    except Exception:
        return render_template(
            "result.html",
            error="Could not read this PDF. Please upload a valid text-based resume PDF.",
        )

    if not extracted_text.strip():
        return render_template(
            "result.html",
            error="Could not extract readable text from this PDF. Please upload a text-based resume PDF.",
        )

    try:
        analysis = analyze_resume_with_gemini(extracted_text, target_role, job_description)
    except RuntimeError as error:
        return render_template(
            "result.html",
            error=str(error),
        )
    except genai_errors.APIError as error:
        return render_template(
            "result.html",
            error=f"Gemini API error: {error.message}",
        )
    except json.JSONDecodeError:
        return render_template(
            "result.html",
            error="The AI response could not be parsed. Please try again.",
        )

    history_record = save_history_record(filename, target_role, job_description, analysis)

    return render_template(
        "result.html",
        analysis=analysis,
        history_record=history_record,
    )


@app.route("/history")
def history():
    return render_template("history.html", history=load_history())


@app.route("/history/<record_id>")
def history_detail(record_id):
    history_record = get_history_record(record_id)

    if not history_record:
        return render_template("result.html", error="This history report could not be found."), 404

    return render_template(
        "result.html",
        analysis=history_record["analysis"],
        history_record=history_record,
    )


if __name__ == "__main__":
    app.run(debug=True)
