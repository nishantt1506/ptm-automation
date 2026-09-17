# PTM Automation System

A complete working demo of an end-to-end Parent–Teacher Meeting automation workflow.

## Features
- Parent portal: choose student, date and preferred slot
- Automatic student -> teacher -> class -> room mapping
- Conflict-aware PTM scheduling
- Confirmation notification simulation
- Teacher portal: PTM status, arrival/completion tracking and remarks
- AI-assisted remark structuring with optional OpenRouter integration
- Rule-based fallback when no API key is configured
- Admin dashboard with KPIs, charts, concerns and student history
- SQLite database with seeded dummy data
- Reset demo data button

## Run
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Open the URL shown by Streamlit, normally http://localhost:8501.

No real authentication is used. Select Parent, Teacher or Admin from the sidebar.
