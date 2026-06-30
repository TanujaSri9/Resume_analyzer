# ✦ AI Resume Analyzer

> **Free AI-powered resume analysis for students and freshers.**  
> ATS score · Job match · Skill roadmap · Interview prep · Cover letter · Mock interview — in ~30 seconds.

---

## 🚀 Features

| Feature | Description |
|---|---|
| 📊 **ATS Score** | See how ATS bots rate your resume on keywords, formatting & readability |
| 🎯 **Job Match** | Paste a job description for a precise alignment score |
| 🎤 **Interview Prep** | HR + technical questions tailored to your resume with sample answers |
| 🗺️ **Skill Roadmap** | Prioritised learning plan with timeline and free resources |
| 🏅 **Certifications** | Real certification recommendations mapped to skill gaps |
| ✏️ **Project Enhancer** | AI rewrites weak project bullets into quantified descriptions |
| 📝 **Cover Letter** | One-click personalised cover letter |
| 🤖 **Mock Interview** | AI chat interviewer — 5 questions, live feedback, performance score |
| 🎓 **Fresher Mode** | Projects & certifications weighted more heavily for students |

---

## 🛠️ Tech Stack

- **Backend:** Python · Flask · pdfplumber · python-docx
- **AI:** NVIDIA NIM API (nemotron-3-nano-30b)
- **Frontend:** Vanilla HTML · CSS · JavaScript (no frameworks)
- **Security:** Flask-Limiter · Session-based history · Auto file deletion
- **Production:** Waitress WSGI server

---

## ⚡ Quick Start

### 1. Clone & install
```bash
git clone https://github.com/TanujaSri9/Resume_analyzer.git
cd Resume_analyzer
pip install -r requirements.txt
```

### 2. Set up environment
```bash
copy .env.example .env
```
Edit `.env` and add your **NVIDIA API key** (get one free at [build.nvidia.com](https://build.nvidia.com)):
```
NVIDIA_API_KEY=nvapi-your-key-here
```

### 3. Run (development)
```bash
python app.py
```
Open [http://localhost:5000](http://localhost:5000)

### 4. Run (production)
```bash
python run.py
```

---

## 📁 Project Structure

```
Resume_analyzer/
├── app.py              # Flask app — all routes & AI logic
├── run.py              # Production startup (Waitress WSGI)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── static/
│   ├── style.css       # All styling
│   └── script.js       # Frontend logic & mock interview chat
├── templates/
│   ├── index.html      # Landing page
│   ├── result.html     # Analysis report (4-tab layout)
│   ├── history.html    # Session history
│   ├── cover_letter.html
│   ├── mock_interview.html
│   ├── 404.html
│   └── 500.html
├── uploads/            # Temp uploads (auto-deleted after analysis)
└── data/               # Local history store (gitignored)
```

---

## 🔒 Privacy

- Uploaded resumes are **deleted immediately** after text extraction
- Analysis history is **session-based** — each user only sees their own reports
- No user accounts, no personal data stored permanently

---

## 📦 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `NVIDIA_API_KEY` | ✅ Yes | Your NVIDIA NIM API key |
| `NVIDIA_MODEL` | Optional | Model name (default: nemotron-3-nano-30b-a3b) |
| `NVIDIA_BASE_URL` | Optional | API base URL |
| `SITE_URL` | Optional | Your public URL (for sitemap/robots.txt) |
| `SECRET_KEY` | Optional | Session secret (auto-generated if not set) |

---

## 🤝 Contributing

Pull requests are welcome! For major changes, please open an issue first.

---

## 📄 License

MIT — free to use, modify, and deploy.
