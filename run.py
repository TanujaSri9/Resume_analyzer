"""
run.py — Production starter for AI Resume Analyzer
Uses waitress (Windows-compatible WSGI server) if installed,
falls back to Flask dev server.

Usage:
    python run.py            # production mode
    python app.py            # Flask dev mode (auto-reload)
"""
import os
import sys

PORT = int(os.getenv("PORT", 5000))
HOST = os.getenv("HOST", "0.0.0.0")

if __name__ == "__main__":
    from app import app

    try:
        from waitress import serve
        print(f"✦ AI Resume Analyzer — production server")
        print(f"✦ Listening on http://{HOST}:{PORT}")
        print(f"✦ Powered by Waitress WSGI")
        serve(app, host=HOST, port=PORT, threads=6, connection_limit=100)
    except ImportError:
        print("⚠ waitress not installed — falling back to Flask dev server")
        print("  Run:  pip install waitress   for production use")
        print(f"✦ Listening on http://127.0.0.1:{PORT}")
        app.run(host="127.0.0.1", port=PORT, debug=False)
