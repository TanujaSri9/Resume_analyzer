# AI Resume Analyzer

A Flask web app that analyzes PDF resumes with Gemini and generates ATS-style feedback, job-description matching, role-fit scoring, interview preparation, and saved report history.

## Features

- PDF resume upload and text extraction
- Role-based resume analysis
- Job description matching
- ATS score, job match score, and role fit score
- Strengths, weaknesses, missing skills, matched keywords, and improvement suggestions
- Resume-specific interview questions with interviewer-friendly sample answers
- Interview Q&A PDF download
- Local analysis history
- Loading overlay while analysis is running

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Create a `.env` file from `.env.example` and add your Gemini API key:

```bash
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

3. Run the app:

```bash
python app.py
```

4. Open:

```text
http://127.0.0.1:5000/
```

## Privacy Notes

The app stores analysis history locally in `data/history.json`. This file is ignored by Git because it can contain resume and job-description information.
