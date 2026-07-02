from flask import Flask, Response, render_template, request, url_for, session, jsonify
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
import logging
import re

# ── optional deps ──────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).with_name(".env"), override=True)
except ImportError:
    pass

try:
    from docx import Document as DocxDocument
    DOCX_SUPPORTED = True
except ImportError:
    DOCX_SUPPORTED = False

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    LIMITER_AVAILABLE = True
except ImportError:
    LIMITER_AVAILABLE = False

# ── logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── app config ─────────────────────────────────────────────────
app = Flask(__name__)

UPLOAD_FOLDER   = "uploads"
ALLOWED_EXT     = {"pdf", "docx", "doc"} if DOCX_SUPPORTED else {"pdf"}
DATA_DIR        = Path(__file__).with_name("data")
HISTORY_FILE    = DATA_DIR / "history.json"
SECRET_KEY_FILE = DATA_DIR / ".secret_key"

app.config["UPLOAD_FOLDER"]      = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True

NVIDIA_MODEL    = os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-nano-30b-a3b")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1").rstrip("/")
SITE_URL        = os.getenv("SITE_URL", "").rstrip("/")

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
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _get_or_create_secret_key() -> str:
    if os.getenv("SECRET_KEY"):
        return os.getenv("SECRET_KEY")
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_text().strip()
    key = uuid4().hex + uuid4().hex
    SECRET_KEY_FILE.write_text(key)
    return key


app.secret_key = _get_or_create_secret_key()

# ── rate limiter ───────────────────────────────────────────────
if LIMITER_AVAILABLE:
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["300 per day"],
        storage_uri="memory://",
    )
    def rate_limit(rule):
        return limiter.limit(rule)
else:
    import functools
    def rate_limit(rule):
        def decorator(fn):
            @functools.wraps(fn)
            def wrapper(*a, **kw):
                return fn(*a, **kw)
            return wrapper
        return decorator


# ════════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════════

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXT


def extract_text_from_file(filepath: str, ext: str) -> str:
    """Extract plain text from PDF or DOCX."""
    if ext == "pdf":
        text = ""
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text
    if ext in {"docx", "doc"} and DOCX_SUPPORTED:
        doc = DocxDocument(filepath)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    raise ValueError(f"Unsupported file type: {ext}")


def load_history() -> list:
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def get_user_history() -> list:
    """Return only the records belonging to the current browser session."""
    user_ids = set(session.get("history_ids", []))
    if not user_ids:
        return []
    return [r for r in load_history() if r.get("id") in user_ids]


def save_history_record(filename, target_role, job_description, analysis, is_fresher=False):
    record = {
        "id": uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "target_role": target_role,
        "is_fresher": is_fresher,
        "has_job_description": bool(job_description),
        "job_description_preview": textwrap.shorten(job_description, 220) if job_description else "",
        "analysis": analysis,
    }

    all_records = load_history()
    all_records.insert(0, record)
    all_records = all_records[:200]          # global cap
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(all_records, f, indent=2)

    # Register in user session
    ids = session.get("history_ids", [])
    ids.insert(0, record["id"])
    session["history_ids"] = ids[:25]
    session.modified = True

    return record


def get_history_record(record_id: str):
    for r in load_history():
        if r.get("id") == record_id:
            return r
    return None


def extract_json_object(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end   = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start: end + 1])


def clean_generation_text(text: str) -> str:
    """Strip out any model self-correction, drafting notes, or word-counting comments."""
    lines = text.split("\n")
    cleaned_lines = []
    
    planning_markers = [
        "we need to", "let's craft", "let's draft", "word count",
        "i'll write and then", "drafting notes", "let's count", "that's 11 words", 
        "that's maybe", "read through my prompt", "key strengths:", "let's write",
        "let's draft", "let's aim", "aim for ~"
    ]
    
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            cleaned_lines.append("")
            continue
            
        line_lower = line_strip.lower()
        
        # 1. If the line contains a long quote, let's extract it (this is the actual content)
        quotes = re.findall(r'"([^"]{25,})"', line_strip)
        if quotes:
            for q in quotes:
                cleaned_lines.append(q.strip())
            continue
            
        # 2. Skip lines that are just numbers/counting or planning commentary
        if "i(1)" in line_lower or "am2" in line_lower or "react,7" in line_lower or "count words:" in line_lower:
            continue
            
        if any(marker in line_lower for marker in planning_markers):
            continue
            
        # 3. Clean common prefixes from the line
        line_clean = re.sub(r'^(Paragraph \d+:|Sentence \d+:|Draft:|Quote:)\s*', '', line_strip, flags=re.IGNORECASE)
        
        # If the line is wrapped in quotes, strip them
        if line_clean.startswith('"') and line_clean.endswith('"'):
            line_clean = line_clean[1:-1].strip()
        elif line_clean.startswith("'") and line_clean.endswith("'"):
            line_clean = line_clean[1:-1].strip()
            
        if line_clean:
            cleaned_lines.append(line_clean)
            
    # Combine back and clean up consecutive empty lines
    result = "\n".join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def create_nvidia_chat_completion(messages: list, max_tokens: int = 4096) -> str:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY is not set. Add it to your .env file.")

    payload = {
        "model": NVIDIA_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "top_p": 0.7,
        "max_tokens": max_tokens,
        "stream": False,
    }
    data = json.dumps(payload).encode("utf-8")
    req  = url_request.Request(
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
        with url_request.urlopen(req, timeout=120) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except url_error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        raise RuntimeError(f"NVIDIA API error ({e.code}): {body}") from e
    except url_error.URLError as e:
        raise RuntimeError(f"Connection to NVIDIA API failed: {e.reason}") from e

    try:
        return response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError("NVIDIA API returned unexpected response format.") from e


# ════════════════════════════════════════════════════════════════
#  PDF BUILDER
# ════════════════════════════════════════════════════════════════

def pdf_escape(text: str) -> str:
    cleaned = str(text).replace("\r", " ").replace("\n", " ")
    cleaned = cleaned.encode("latin-1", "replace").decode("latin-1")
    return cleaned.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_interview_pdf(analysis: dict, filename: str, target_role: str) -> bytes:
    hr_qs     = analysis.get("hr_questions", [])
    tech_qs   = analysis.get("technical_questions", [])
    legacy_qs = analysis.get("interview_questions", [])

    all_questions = []
    if hr_qs or tech_qs:
        for q in hr_qs:
            all_questions.append({"focus_area": "HR Round", "question": q.get("question",""), "answer": q.get("answer","")})
        for q in tech_qs:
            all_questions.append({"focus_area": q.get("focus_area","Technical"), "question": q.get("question",""), "answer": q.get("answer","")})
    else:
        all_questions = legacy_qs

    pages, lines = [], []
    y = 780

    def write_line(text, size=10, bold=False, gap=15, x=50):
        nonlocal lines, y
        if y < 58:
            _flush_page()
        lines.append({"text": text, "size": size, "bold": bold, "x": x, "y": y})
        y -= gap

    def _flush_page():
        nonlocal lines, y
        cmds = []
        for ln in lines:
            f = "F2" if ln.get("bold") else "F1"
            cmds.append(f"BT /{f} {ln['size']} Tf {ln['x']} {ln['y']} Td ({pdf_escape(ln['text'])}) Tj ET")
        pages.append("\n".join(cmds).encode("latin-1", "replace"))
        lines = []
        y = 780

    write_line("AI Resume Analyzer — Interview Preparation", size=16, bold=True, gap=24)
    write_line(f"Resume: {filename or 'Uploaded resume'}", size=10, gap=14)
    write_line(f"Target role: {target_role or analysis.get('target_role','General')}", size=10, gap=20)
    write_line("High-probability interview questions with sample answers.", size=10, gap=24)

    if not all_questions:
        write_line("No interview questions were generated for this report.", size=11, bold=True)
    else:
        for idx, item in enumerate(all_questions, 1):
            write_line(f"{idx}. {item.get('focus_area','Interview')}", size=12, bold=True, gap=18)
            for w in textwrap.wrap(f"Q: {item.get('question','')}", 92):
                write_line(w, size=10, bold=True, gap=13)
            for w in textwrap.wrap(f"A: {item.get('answer','')}", 94):
                write_line(w, size=10, gap=13)
            y -= 8

    if lines:
        _flush_page()

    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [" +
        b" ".join(f"{3+i*2} 0 R".encode() for i in range(len(pages))) +
        f"] /Count {len(pages)} >>".encode(),
    ]
    for i, content in enumerate(pages):
        pn, cn = 3 + i*2, 4 + i*2
        page = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
            f"/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> >> >> "
            f"/Contents {cn} 0 R >>"
        ).encode()
        stream = b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream"
        objs.extend([page, stream])

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for num, content in enumerate(objs, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{num} 0 obj\n".encode())
        pdf.extend(content)
        pdf.extend(b"\nendobj\n")

    xref_off = len(pdf)
    pdf.extend(f"xref\n0 {len(objs)+1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_off}\n%%EOF".encode())
    return bytes(pdf)


# ════════════════════════════════════════════════════════════════
#  AI — RESUME ANALYSIS
# ════════════════════════════════════════════════════════════════

def analyze_resume_with_nvidia(resume_text: str, target_role: str, job_description: str, is_fresher: bool = False) -> dict:
    schema = {
        "type": "object",
        "properties": {
            "ats_score":              {"type": "integer"},
            "job_match_score":        {"type": "integer"},
            "role_fit_score":         {"type": "integer"},
            "target_role":            {"type": "string"},
            "summary":                {"type": "string"},
            "job_description_alignment": {"type": "string"},
            "strengths":              {"type": "array", "items": {"type": "string"}},
            "weaknesses":             {"type": "array", "items": {"type": "string"}},
            "missing_skills":         {"type": "array", "items": {"type": "string"}},
            "matched_keywords":       {"type": "array", "items": {"type": "string"}},
            "missing_job_keywords":   {"type": "array", "items": {"type": "string"}},
            "role_based_recommendations": {"type": "array", "items": {"type": "string"}},
            "improvement_suggestions":    {"type": "array", "items": {"type": "string"}},
            "hr_questions": {"type": "array", "items": {"type": "object", "properties": {"question": {"type": "string"}, "answer": {"type": "string"}}, "required": ["question","answer"]}},
            "technical_questions": {"type": "array", "items": {"type": "object", "properties": {"focus_area": {"type": "string"}, "question": {"type": "string"}, "answer": {"type": "string"}}, "required": ["focus_area","question","answer"]}},
            "project_tips": {"type": "array", "items": {"type": "object", "properties": {"original": {"type": "string"}, "improved": {"type": "string"}, "why": {"type": "string"}}, "required": ["original","improved","why"]}},
            "quantification_tips": {"type": "array", "items": {"type": "object", "properties": {"original": {"type": "string"}, "suggested": {"type": "string"}, "metric_hint": {"type": "string"}}, "required": ["original","suggested","metric_hint"]}},
            "skill_roadmap": {"type": "array", "items": {"type": "object", "properties": {"skill": {"type": "string"}, "priority": {"type": "string"}, "weeks": {"type": "integer"}, "resource": {"type": "string"}}, "required": ["skill","priority","weeks","resource"]}},
            "certifications": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "provider": {"type": "string"}, "skill": {"type": "string"}, "is_free": {"type": "boolean"}, "duration": {"type": "string"}}, "required": ["name","provider","skill","is_free","duration"]}},
        },
        "required": ["ats_score","job_match_score","role_fit_score","target_role","summary","job_description_alignment","strengths","weaknesses","missing_skills","matched_keywords","missing_job_keywords","role_based_recommendations","improvement_suggestions","hr_questions","technical_questions","project_tips","quantification_tips","skill_roadmap","certifications"],
    }

    jd_context = job_description[:8000] if job_description else "No job description provided. Use general expectations for the target role."
    fresher_block = """
FRESHER / STUDENT MODE:
- Weight academic projects as professional experience.
- Credit online certifications, MOOCs, and coursework heavily.
- Value CGPA, academic rank, extracurriculars, open-source work.
- Do NOT penalise for lack of full-time work experience.\n""" if is_fresher else ""

    prompt = f"""You are an expert ATS resume reviewer and career coach for students.

Analyse this resume for: {target_role}
{fresher_block}
Job description: {jd_context}

GENERATE:
- Scores (0-100): ats_score, job_match_score, role_fit_score
- summary: 2-sentence overall assessment
- job_description_alignment: paragraph on JD fit
- strengths, weaknesses, missing_skills, improvement_suggestions: 4-6 items each
- matched_keywords, missing_job_keywords: up to 12 items each
- role_based_recommendations: 4-6 specific tips
- hr_questions: exactly 4 behavioral questions with first-person sample answers
- technical_questions: exactly 4 technical questions with first-person sample answers
- project_tips: up to 3 — find weak project bullets and rewrite them (original, improved, why)
- quantification_tips: up to 3 — find bullets lacking metrics (original, suggested with ~estimates, metric_hint)
- skill_roadmap: up to 5 — priority (High/Medium/Low), weeks (int), free resource name
- certifications: up to 4 — real FUTURE certifications (different from any certifications already listed on the resume) with name, provider, skill covered, is_free, duration. Only suggest certifications they have NOT done yet to help fill their skill gaps for the target role.

Resume:
{resume_text[:14000]}

Return ONLY JSON matching this schema:
{json.dumps(schema, indent=2)}"""

    text = create_nvidia_chat_completion(
        [
            {"role": "system", "content": "You are an expert ATS resume reviewer. Return ONLY valid JSON. No markdown, no commentary."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=8000,
    )
    return extract_json_object(text)


# ════════════════════════════════════════════════════════════════
#  AI — COVER LETTER
# ════════════════════════════════════════════════════════════════

def generate_cover_letter_with_nvidia(analysis: dict, target_role: str, jd_preview: str) -> str:
    strengths = ", ".join(analysis.get("strengths", [])[:3]) or "strong technical skills"
    role = target_role or analysis.get("target_role", "this role")

    prompt = f"""Write a professional cover letter for a student/fresher candidate.

Role: {role}
Key strengths: {strengths}
Job context: {jd_preview or f"General application for {role}"}

Instructions:
1. Write EXACTLY 3 paragraphs (total 260-320 words).
2. Do NOT write any greetings, address headers, dates, contact details, signing-off headers, drafting notes, word counts, or chain-of-thought.
3. Start IMMEDIATELY with the first word of the cover letter.
4. Avoid placeholders like [Company Name]. If company name is not available, refer generically to "your company", "your team", or "your organization".
5. Keep the tone professional, confident, and genuine.

Paragraph 1: Engaging hook — why this specific role excites them.
Paragraph 2: 2-3 most relevant skills/projects matching the role.
Paragraph 3: Enthusiasm, openness to interview, polite call to action."""

    system_msg = (
        "You are a professional career coach. You write ONLY the final cover letter body text. "
        "You NEVER output greeting headers, addresses, signature blocks, drafting notes, self-correction, or word counts. "
        "Your response must start directly with the first sentence of the cover letter."
    )

    raw_text = create_nvidia_chat_completion(
        [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        max_tokens=1024,
    )
    return clean_generation_text(raw_text)


# ════════════════════════════════════════════════════════════════
#  AI — PROFESSIONAL SUMMARY GENERATOR
# ════════════════════════════════════════════════════════════════

def generate_professional_summary_text(analysis: dict, target_role: str) -> str:
    strengths = ", ".join(analysis.get("strengths", [])[:3]) or "technical and analytical skills"
    skills    = ", ".join(analysis.get("matched_keywords", [])[:6]) or "relevant technical skills"
    role      = target_role or analysis.get("target_role", "the target role")

    prompt = f"""Write a professional resume summary/career objective for a student/fresher applying for: {role}

Resume details to base it on:
- Top Strengths: {strengths}
- Core Skills: {skills}

Instructions:
1. Write EXACTLY 3 sentences (65-85 words total).
2. Write in first person (using "I", "my", "me").
3. Do NOT include any self-correction, drafting steps, headers, bullet points, numbers, word-counts, introductory text, or concluding notes.
4. Start IMMEDIATELY with the first word of the summary paragraph.
5. The summary must be highly professional and tailored to be ATS-friendly.

Sentence 1: Professional identity + specialization.
Sentence 2: Key technical skills and a notable project or achievement.
Sentence 3: Career goal aligned with the target role."""

    system_msg = (
        "You are an expert resume writer. You output ONLY the final resume summary text. "
        "You NEVER write comments, drafting steps, chain-of-thought, or word counts. "
        "If you do, you fail. Your output must start directly with the first sentence."
    )

    raw_text = create_nvidia_chat_completion(
        [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": prompt},
        ],
        max_tokens=256,
    )
    return clean_generation_text(raw_text)


# ════════════════════════════════════════════════════════════════
#  AI — MOCK INTERVIEW CHAT
# ════════════════════════════════════════════════════════════════

def mock_interview_response(role: str, messages: list, question_num: int) -> dict:
    is_final = question_num > 5

    system_content = f"""You are a professional AI interviewer conducting a mock interview for: {role}

Rules:
- Ask ONE question per turn, mixing behavioral (HR) and technical questions relevant to {role}
- After each user answer (except the first question), give 2-3 sentences of constructive feedback
- After question 5, give a final performance summary instead of another question

Current question number: {question_num} of 5{"  — GIVE FINAL SUMMARY NOW." if is_final else ""}

Respond with ONLY valid JSON (no markdown):
{{"feedback": "<feedback on their last answer, empty string before Q1>", "question": "<next question, empty if final>", "is_final": {"true" if is_final else "false"}, "summary": "<detailed summary with rating X/10, strong areas, weak areas, top tip — only when is_final true, else empty string>"}}"""

    ai_messages = [{"role": "system", "content": system_content}]
    ai_messages += messages[-10:]   # keep last 10 for context

    if not messages:
        ai_messages.append({"role": "user", "content": "Start the interview. Ask the first question."})

    text = create_nvidia_chat_completion(ai_messages, max_tokens=600)
    result = extract_json_object(text)
    result.setdefault("feedback", "")
    result.setdefault("question", "")
    result.setdefault("is_final", is_final)
    result.setdefault("summary", "")
    return result


# ════════════════════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════════════════════

@app.route("/")
def home():
    return render_template("index.html", target_roles=TARGET_ROLES, docx_supported=DOCX_SUPPORTED)


@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()})


@app.route("/robots.txt")
def robots_txt():
    base = SITE_URL or request.url_root.rstrip("/")
    return Response(
        f"User-agent: *\nAllow: /\nDisallow: /analyze\nDisallow: /history\n\nSitemap: {base}/sitemap.xml\n",
        mimetype="text/plain",
    )


@app.route("/sitemap.xml")
def sitemap_xml():
    base = SITE_URL or request.url_root.rstrip("/")
    updated = datetime.now(timezone.utc).date().isoformat()
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{base}/</loc><lastmod>{updated}</lastmod><priority>1.0</priority></url>
  <url><loc>{base}/mock-interview</loc><lastmod>{updated}</lastmod><priority>0.8</priority></url>
</urlset>"""
    return Response(xml, mimetype="application/xml")


# ── analysis ────────────────────────────────────────────────────

@app.route("/analyze", methods=["POST"])
@rate_limit("5 per hour")
def analyze_resume():
    if "resume" not in request.files:
        return render_template("result.html", error="No file was uploaded.")

    file = request.files["resume"]
    if not file or file.filename == "":
        return render_template("result.html", error="No file was selected.")

    if not allowed_file(file.filename):
        exts = "PDF or DOCX" if DOCX_SUPPORTED else "PDF"
        return render_template("result.html", error=f"Please upload a {exts} resume.")

    target_role  = request.form.get("target_role", "General").strip()
    if target_role not in TARGET_ROLES:
        target_role = "General"
    job_description = request.form.get("job_description", "").strip()
    is_fresher      = request.form.get("is_fresher") == "true"

    original_name = secure_filename(file.filename)
    ext           = original_name.rsplit(".", 1)[1].lower()
    unique_name   = f"{uuid4().hex[:8]}_{original_name}"
    filepath      = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    file.save(filepath)

    try:
        extracted_text = extract_text_from_file(filepath, ext)
    except Exception as e:
        return render_template("result.html", error=f"Could not read this file: {e}")
    finally:
        try:
            os.remove(filepath)
        except OSError:
            pass

    if not extracted_text.strip():
        return render_template(
            "result.html",
            error="Could not extract readable text. Please upload a text-based resume (not a scanned image).",
        )

    try:
        analysis = analyze_resume_with_nvidia(extracted_text, target_role, job_description, is_fresher)
    except RuntimeError as e:
        return render_template("result.html", error=str(e))
    except json.JSONDecodeError:
        return render_template("result.html", error="AI response could not be parsed. Please try again.")

    history_record = save_history_record(original_name, target_role, job_description, analysis, is_fresher)
    return render_template("result.html", analysis=analysis, history_record=history_record)


# ── history ─────────────────────────────────────────────────────

@app.route("/history")
def history():
    return render_template("history.html", history=get_user_history())


@app.route("/history/<record_id>")
def history_detail(record_id):
    user_ids = set(session.get("history_ids", []))
    if record_id not in user_ids:
        return render_template("404.html"), 404
    record = get_history_record(record_id)
    if not record:
        return render_template("404.html"), 404
    return render_template("result.html", analysis=record["analysis"], history_record=record)


@app.route("/history/<record_id>/interview-pdf")
def download_interview_pdf(record_id):
    user_ids = set(session.get("history_ids", []))
    if record_id not in user_ids:
        return render_template("404.html"), 404
    record = get_history_record(record_id)
    if not record:
        return render_template("404.html"), 404
    pdf  = build_interview_pdf(record["analysis"], record.get("filename",""), record.get("target_role",""))
    name = secure_filename(record.get("target_role","interview") + "-questions") + ".pdf"
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@app.route("/history/<record_id>/cover-letter")
def cover_letter(record_id):
    user_ids = set(session.get("history_ids", []))
    if record_id not in user_ids:
        return render_template("404.html"), 404
    record = get_history_record(record_id)
    if not record:
        return render_template("404.html"), 404
    try:
        letter = generate_cover_letter_with_nvidia(
            record.get("analysis", {}),
            record.get("target_role", ""),
            record.get("job_description_preview", ""),
        )
    except RuntimeError as e:
        return render_template("cover_letter.html", error=str(e), record=record)
    return render_template("cover_letter.html", letter=letter, record=record)


@app.route("/history/<record_id>/summary", methods=["POST"])
@rate_limit("10 per hour")
def generate_summary(record_id):
    user_ids = set(session.get("history_ids", []))
    if record_id not in user_ids:
        return jsonify({"error": "Not found"}), 404
    record = get_history_record(record_id)
    if not record:
        return jsonify({"error": "Record not found"}), 404
    try:
        text = generate_professional_summary_text(record.get("analysis", {}), record.get("target_role", ""))
        return jsonify({"summary": text})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


# ── mock interview ───────────────────────────────────────────────

@app.route("/mock-interview")
def mock_interview():
    return render_template("mock_interview.html", target_roles=TARGET_ROLES)


@app.route("/mock-interview/chat", methods=["POST"])
@rate_limit("30 per hour")
def mock_interview_chat():
    data = request.get_json(silent=True) or {}
    role         = data.get("role", "General")
    messages     = data.get("messages", [])
    question_num = int(data.get("question_num", 1))

    try:
        result = mock_interview_response(role, messages, question_num)
        return jsonify(result)
    except (RuntimeError, json.JSONDecodeError) as e:
        return jsonify({"error": str(e)}), 500


# ── error handlers ───────────────────────────────────────────────

@app.errorhandler(RequestEntityTooLarge)
def file_too_large(_):
    return render_template("result.html", error="File too large. Please upload a resume under 8 MB."), 413


@app.errorhandler(404)
def not_found(_):
    return render_template("404.html"), 404


@app.errorhandler(500)
def server_error(_):
    return render_template("500.html"), 500


if LIMITER_AVAILABLE:
    @app.errorhandler(429)
    def too_many_requests(_):
        return render_template("result.html",
            error="You've reached the analysis limit (5 per hour). Please try again later."), 429


if __name__ == "__main__":
    app.run(debug=True, port=5000)
