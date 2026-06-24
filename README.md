# 🔍 FactCheck Agent

An AI-powered fact-checking web app that **automatically verifies claims in any PDF** against live web data.

## Live Demo
> Deploy to Streamlit Cloud (see below) — enter your URL here after deployment.

## What It Does

| Step | Action |
|------|--------|
| **Extract** | Reads uploaded PDF and identifies all verifiable claims (stats, dates, financial figures, research citations) |
| **Verify** | Uses Claude claude-sonnet-4-6 with live web search to cross-reference each claim against current data |
| **Report** | Flags each claim as ✅ Verified / ⚠️ Inaccurate / ❌ False / ❓ Uncertain with explanation and sources |

## Tech Stack
- **Frontend**: Streamlit
- **AI**: Claude claude-sonnet-4-6 (Anthropic) with `web_search_20250305` tool
- **PDF Parsing**: pypdf
- **Deployment**: Streamlit Cloud

## Local Setup

```bash
git clone <your-repo>
cd factcheck-app
pip install -r requirements.txt
streamlit run app.py
```

You'll be prompted to enter your Anthropic API key in the UI (never stored).

## Deploy to Streamlit Cloud (Free)

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect repo → set `app.py` as the main file
4. Deploy — get a public URL instantly

No secret env vars needed; the API key is entered by users in the UI.

## Evaluation / Trap Document Test

The app is specifically designed to catch:
- **Outdated statistics** (e.g., old market size figures that have since changed)
- **Hallucinated numbers** (e.g., made-up percentages or rankings)
- **False attributions** (e.g., stats attributed to wrong sources)
- **Fabricated dates** (e.g., wrong year for a product launch or event)

Upload any PDF and the agent will surface discrepancies with real-world data.

## Project Structure

```
factcheck-app/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## How It Works (Architecture)

```
PDF Upload
    │
    ▼
Text Extraction (pypdf)
    │
    ▼
Claim Extraction (Claude claude-sonnet-4-6 — structured JSON output)
    │
    ▼
Per-Claim Verification Loop:
  Claude claude-sonnet-4-6 + web_search_20250305 tool
  → verdict: Verified / Inaccurate / False / Uncertain
  → explanation + real fact + source URLs
    │
    ▼
Dashboard Report + JSON Download
```

---
Built for CogCulture Product Management Trainee Assessment · 2025
