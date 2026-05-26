from flask import Flask, Response, render_template, request, url_for
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from urllib import error as url_error
from urllib import request as url_request
import pdfplumber
import os
import json
import textwrap

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
NVIDIA_MODEL = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-nano-30b-a3b")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
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


def extract_json_object(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            raise

        return json.loads(text[start : end + 1])


def create_nvidia_chat_completion(messages, max_tokens=4096):
    api_key = os.getenv("NVIDIA_API_KEY")

    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is missing in .env file.")

    payload = {
        "model": NVIDIA_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "top_p": 0.7,
        "max_tokens": max_tokens,
        "stream": False,
    }

    data = json.dumps(payload).encode("utf-8")
    request = url_request.Request(
        f"{NVIDIA_BASE_URL}/chat/completions",
        data=data,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with url_request.urlopen(request, timeout=90) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except url_error.HTTPError as error:
        error_body = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"NVIDIA API error ({error.code}): {error_body}") from error
    except url_error.URLError as error:
        raise RuntimeError(f"Could not connect to NVIDIA API: {error.reason}") from error

    try:
        return response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("NVIDIA API returned an unexpected response format.") from error


def pdf_escape(text):
    cleaned_text = str(text).replace("\r", " ").replace("\n", " ")
    cleaned_text = cleaned_text.encode("latin-1", "replace").decode("latin-1")
    return cleaned_text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def add_pdf_page(pages, lines):
    commands = []

    for line in lines:
        font = "F2" if line.get("bold") else "F1"
        size = line.get("size", 10)
        x = line.get("x", 50)
        y = line.get("y", 750)
        text = pdf_escape(line.get("text", ""))
        commands.append(f"BT /{font} {size} Tf {x} {y} Td ({text}) Tj ET")

    pages.append("\n".join(commands).encode("latin-1", "replace"))


def build_interview_pdf(analysis, filename, target_role):
    interview_questions = analysis.get("interview_questions", [])
    pages = []
    lines = []
    y = 780

    def write_line(text, size=10, bold=False, gap=15, x=50):
        nonlocal lines, y

        if y < 58:
            add_pdf_page(pages, lines)
            lines = []
            y = 780

        lines.append({"text": text, "size": size, "bold": bold, "x": x, "y": y})
        y -= gap

    write_line("AI Resume Analyzer - Interview Preparation", size=16, bold=True, gap=24)
    write_line(f"Resume: {filename or 'Uploaded resume'}", size=10, gap=14)
    write_line(f"Target role: {target_role or analysis.get('target_role', 'General')}", size=10, gap=20)
    write_line("High-probability interview questions and interviewer-friendly answers.", size=10, gap=24)

    if not interview_questions:
        write_line("No interview questions were generated for this report.", size=11, bold=True)
    else:
        for index, item in enumerate(interview_questions, start=1):
            focus_area = item.get("focus_area", "Interview")
            question = item.get("question", "")
            answer = item.get("answer", "")

            write_line(f"{index}. {focus_area}", size=12, bold=True, gap=18)

            for wrapped_line in textwrap.wrap(f"Question: {question}", width=92):
                write_line(wrapped_line, size=10, bold=True, gap=13)

            for wrapped_line in textwrap.wrap(f"Answer: {answer}", width=94):
                write_line(wrapped_line, size=10, gap=13)

            y -= 8

    if lines:
        add_pdf_page(pages, lines)

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids ["
        + b" ".join(f"{3 + index * 2} 0 R".encode("ascii") for index in range(len(pages)))
        + f"] /Count {len(pages)} >>".encode("ascii"),
    ]

    for index, content in enumerate(pages):
        page_object_number = 3 + index * 2
        content_object_number = page_object_number + 1
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
            f"/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> >> >> "
            f"/Contents {content_object_number} 0 R >>"
        ).encode("ascii")
        stream = b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream"
        objects.extend([page, stream])

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]

    for object_number, content in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{object_number} 0 obj\n".encode("ascii"))
        pdf.extend(content)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")

    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("ascii")
    )

    return bytes(pdf)


def analyze_resume_with_nvidia(resume_text, target_role, job_description):
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
            "interview_questions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "focus_area": {"type": "string"},
                        "question": {"type": "string"},
                        "answer": {"type": "string"},
                    },
                    "required": ["focus_area", "question", "answer"],
                },
            },
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
            "interview_questions",
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

Generate 8 interview questions that have a high chance of being asked for this candidate.
Base them on the resume, selected role, job description, projects, skills, gaps, and experience level.
For each answer, write an interviewer-friendly sample answer in first person.
The answer should sound confident, specific, and honest. Do not invent exact metrics or companies.
If the resume lacks a detail, phrase the answer as a template the candidate can personalize.

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
- interview_questions: array of objects with focus_area, question, and answer strings
- improvement_suggestions: array of strings

Target role:
{target_role}

Job description:
{job_description_context}

Resume:
{resume_text[:15000]}
"""

    response_text = create_nvidia_chat_completion(
        [
            {
                "role": "system",
                "content": (
                    "You are an expert ATS resume reviewer. Return only valid JSON. "
                    "Do not include markdown fences, explanations, or text outside the JSON object."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{prompt}\n\nJSON schema to follow exactly:\n"
                    f"{json.dumps(schema, indent=2)}"
                ),
            },
        ],
    )

    return extract_json_object(response_text)


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
        analysis = analyze_resume_with_nvidia(extracted_text, target_role, job_description)
    except RuntimeError as error:
        return render_template(
            "result.html",
            error=str(error),
        )
    except json.JSONDecodeError:
        return render_template(
            "result.html",
            error="The NVIDIA AI response could not be parsed. Please try again.",
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


@app.route("/history/<record_id>/interview-pdf")
def download_interview_pdf(record_id):
    history_record = get_history_record(record_id)

    if not history_record:
        return render_template("result.html", error="This interview PDF could not be found."), 404

    analysis = history_record.get("analysis", {})
    filename = history_record.get("filename", "resume")
    target_role = history_record.get("target_role", analysis.get("target_role", "General"))
    pdf = build_interview_pdf(analysis, filename, target_role)
    download_name = f"{secure_filename(target_role or 'interview-prep') or 'interview-prep'}-questions.pdf"

    return Response(
        pdf,
        mimetype="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{download_name}"',
        },
    )


if __name__ == "__main__":
    app.run(debug=True)
