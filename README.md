# AI Resume Analyzer 🎯

An AI-powered resume analyzer built for students and freshers. Get your ATS score, job match analysis, interview prep, skill roadmap, cover letter, and practice with a live mock interview — all in 30 seconds. **Free. No signup.**

## ✦ Features

| Feature | Description |
|---|---|
| 📊 **ATS Score** | See how ATS bots rate your resume |
| 🎯 **Job Match** | Paste a JD for precise keyword alignment |
| 🎤 **Interview Prep** | HR + Technical questions with sample answers |
| 🗺️ **Skill Roadmap** | Prioritised learning plan with free resources |
| 🏅 **Certifications** | Role-specific cert recommendations |
| ✏️ **Project Enhancer** | AI rewrites weak project descriptions |
| 📝 **Cover Letter** | One-click personalised cover letter |
| 📝 **Summary Generator** | 3-sentence professional "About Me" paragraph |
| 🤖 **Mock Interview** | Live AI interview with per-answer feedback & score |

## 🚀 Getting Started (Local)

```bash
# 1. Clone the repo
git clone https://github.com/YOUR_USERNAME/ai-resume-analyzer.git
cd ai-resume-analyzer

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment variables
copy .env.example .env
# Edit .env and add your NVIDIA_API_KEY

# 4. Run the app
python app.py         # dev mode
python run.py         # production mode (Waitress)
```

Open [http://localhost:5000](http://localhost:5000)

## 🔑 Environment Variables

Create a `.env` file (see `.env.example`):

```
NVIDIA_API_KEY=nvapi-your-key-here
NVIDIA_MODEL=nvidia/nemotron-3-nano-30b-a3b
NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1
SITE_URL=https://your-deployed-url.com
SECRET_KEY=your-random-secret-key
```

Get your free NVIDIA API key at: [build.nvidia.com](https://build.nvidia.com)

## 🏗️ Tech Stack

- **Backend** — Python, Flask, Flask-Limiter
- **AI** — NVIDIA NIM API (Nemotron)
- **PDF/DOCX** — pdfplumber, python-docx
- **Frontend** — Vanilla HTML, CSS, JavaScript
- **Production** — Waitress WSGI

## 🔒 Privacy

- Uploaded resumes are **deleted immediately** after text extraction
- No resume file is ever stored on disk beyond a few seconds
- History is private to each browser session — no shared data

## 📄 License

MIT — free to use, modify, and deploy.
