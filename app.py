#!/usr/bin/env python3
# ============================================================
# app.py  —  NeuroAgent Entry Point
# ============================================================
# Run this file to start the server AND open the browser:
#
#     python app.py
#
# What this file does:
#   1. Adds the project root to sys.path.
#   2. Imports and initialises the Flask app + SQLite DB.
#   3. Mounts the frontend (HTML / CSS / JS) on static routes.
#   4. Opens http://127.0.0.1:5000 in the default browser.
#   5. Starts the Flask development server.
# ============================================================

import os
import sys
import threading
import webbrowser
import time

# ── Ensure the project root is in the Python path ─────────────
# This lets `import backend.xxx` work from anywhere.
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

# ── Load config early so .env is read before anything else ────
from backend.config import APP_HOST, APP_PORT, DEBUG

# ── Import and create the Flask app ───────────────────────────
from backend.app import create_app
from flask import send_from_directory

app = create_app()   # Initialises DB, registers API routes

# ── Serve the frontend ─────────────────────────────────────────
# The frontend lives in frontend/templates/index.html and uses
# static files under frontend/static/.

FRONTEND_DIR  = os.path.join(ROOT, "frontend")
TEMPLATE_DIR  = os.path.join(FRONTEND_DIR, "templates")
STATIC_DIR    = os.path.join(FRONTEND_DIR, "static")


@app.route("/")
def index():
    """Serve the main SPA (Single Page Application)."""
    return send_from_directory(TEMPLATE_DIR, "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve CSS, JS, images, and other static assets."""
    return send_from_directory(STATIC_DIR, filename)

@app.route("/favicon.ico")
def favicon():
    """Avoid noisy 404s when no favicon is provided."""
    return ("", 204)


# ── Browser auto-open ──────────────────────────────────────────

def _open_browser(url: str, delay: float = 1.5):
    """
    Wait briefly for the server to start, then open the browser.
    Runs in a background thread so it doesn't block Flask startup.
    """
    time.sleep(delay)
    webbrowser.open(url)
    print(f"[App] Browser opened → {url}")


# ══════════════════════════════════════════════════════════════
# STARTUP BANNER
# ══════════════════════════════════════════════════════════════

def _print_banner():
    url = f"http://{APP_HOST}:{APP_PORT}"
    print("\n" + "═" * 60)
    print(" A G E N T")
    print("═" * 60)
    print(f"  🌐  URL      : {url}")
    print(f"  🧠  Backend  : Flask + LangGraph")
    print(f"  🔍  Search   : Tavily")
    print(f"  💾  Memory   : Pinecone")
    print(f"  📧  Email    : Gmail OAuth2")
    print(f"  🎙  Voice    : SpeechRecognition + gTTS")
    print("═" * 60)
    print("  Press Ctrl+C to stop the server.\n")


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    _print_banner()

    url = f"http://{APP_HOST}:{APP_PORT}"

    # Open browser in background thread
    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    # Start Flask server (blocking call)
    app.run(
        host=APP_HOST,
        port=APP_PORT,
        debug=DEBUG,
        use_reloader=False,   # Disable reloader to avoid double browser open
    )
