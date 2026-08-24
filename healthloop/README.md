# HealthLoop — Hackathon Starter Build

Stack: **Python (FastAPI)** backend + **HTML/CSS/JS** frontend + **SQLite** database (zero setup, just a file).

## What's already working

- **Module 1 — Report Analyzer & Recovery Companion**: photo → OCR (Tesseract) → Groq explains it in plain language, in the user's chosen language, shows primary finding + "also noticed" secondary findings + diet/meal tips, auto-detects medicines and sets reminders.
- **Module 2 — Mental health chat**: supportive chat with Groq, risk detection with a crisis-resource escalation screen (Tele-MANAS 14416).
- **Module 3 — Nearby Care Finder**: adaptive symptom interview recommends a specialty; if it looks like an emergency, automatically switches to showing only 24/7 emergency-capable hospitals instead of just "open now" places. Uses the free OpenStreetMap Overpass API (no key, no billing account) for hospital data + opening hours.
- Voice: uses the **browser's built-in Web Speech API** (`speechSynthesis`) for free, zero-setup text-to-speech.

**Note on the hospital finder**: `overpass-api.de` could not be verified as reachable from the sandboxed environment this was built in (it blocks unlisted outbound domains) — this is a limitation of that build environment only, not of Overpass itself, which is a public, unauthenticated API reachable from any normal machine. Test `/api/hospitals/nearby` on your actual dev machine before demo day, and have a backup plan (e.g. a small hardcoded hospital list for your demo city) in case OSM data coverage is thin for the area you're demoing in.


## Setup (do this once)

1. **Get a free Groq API key**: https://console.groq.com → sign up → create an API key.
2. In `backend/`, copy `.env.example` to `.env` and paste your key in:
   ```
   cp backend/.env.example backend/.env
   # then edit backend/.env and set GROQ_API_KEY=your_actual_key
   ```
3. Install Python dependencies:
   ```
   cd backend
   pip install -r requirements.txt
   ```
4. Make sure Tesseract OCR is installed on your machine:
   - Mac: `brew install tesseract`
   - Linux: `sudo apt install tesseract-ocr`
   - Windows: install from https://github.com/UB-Mannheim/tesseract/wiki

## Running it

1. Start the backend:
   ```
   cd backend
   uvicorn main:app --reload --port 8000
   ```
2. Open the frontend: just open `frontend/index.html` directly in your browser, OR serve it so paths behave consistently:
   ```
   cd frontend
   python3 -m http.server 5500
   ```
   then visit `http://localhost:5500`

3. First time in the app: it'll ask for your name/age/language — this creates a user in the local SQLite database (`backend/healthloop.db`).

## Database

Uses **SQLAlchemy**, so you can switch between SQLite, PostgreSQL, or MySQL just by setting `DATABASE_URL` in `backend/.env` — no code changes needed.

- **Default (SQLite)**: nothing to configure, works out of the box. Best for day-to-day dev/demo since nothing can fail on setup.
- **PostgreSQL**: `DATABASE_URL=postgresql://username:password@localhost:5432/healthloop` (or a free hosted instance from Supabase/Neon/Railway — just paste their connection string in).
- **MySQL**: `DATABASE_URL=mysql+pymysql://username:password@localhost:3306/healthloop`

For your final SIH demo, PostgreSQL is the stronger "production-ready" story since it's a common real-world choice for apps storing structured + JSON-ish data — but SQLite is the safer bet if you just want zero risk of a setup failure right before judging.



```
healthloop/
  backend/
    main.py           <- FastAPI app, all API routes
    groq_client.py     <- all Groq prompts live here (report analysis, triage, mental health)
    ocr.py              <- image -> text extraction
    database.py         <- SQLite tables + connection
    requirements.txt
    .env.example
  frontend/
    index.html          <- dashboard
    upload.html          <- Module 1: report upload + analysis
    reminders.html        <- Module 2: medicine reminders
    triage.html            <- Module 5: symptom triage interview
    mental-health.html      <- Module 3: supportive chat + crisis escalation
    style.css
    app.js               <- shared helpers (API calls, text-to-speech)
```

## What's next for your team to build

- **Hospital lookup (finish Module 5)**: after `triage.html` gets a `recommended_specialty`, call a new backend endpoint that queries Google Places Nearby Search (needs billing account, free quota) or the OpenStreetMap Overpass API (fully free, no key) for hospitals near the user, filtered by rating. Show results as a list with phone number + "Get Directions" link.
- **Weekly check-in scheduling (Module 2)**: currently reminders are one-off; add a scheduler (e.g. APScheduler in Python) to trigger the weekly symptom Q&A automatically and push a browser/mobile notification.
- **Auth**: currently there's no real login/password — just a name-based profile stored in localStorage. Fine for a demo; add real auth if you have time.
- **Deploy for judging**: Render or Railway (both have free tiers) work well for the FastAPI backend; the frontend can be served as static files from the same host or GitHub Pages.

## Team split suggestion

- Person A: polish Module 1 (report upload) — this is your strongest demo feature, make sure it's bulletproof with 3-4 real test report photos.
- Person B: hospital lookup integration for Module 5.
- Person C: weekly check-in scheduling + reminder polish (Module 2).
- Person D: mental health module refinement + pitch deck/flowchart.
