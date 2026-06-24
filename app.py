import streamlit as st
import anthropic
import json
import re
import time
from pypdf import PdfReader
import io

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FactCheck Agent",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Minimal CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.main { padding-top: 1rem; }
.stButton>button {
    background: linear-gradient(135deg, #00C9A7, #008F75);
    color: white; border: none; border-radius: 8px;
    padding: 0.6rem 2rem; font-weight: 600; font-size: 1rem;
    width: 100%;
}
.stButton>button:hover { opacity: 0.9; }
.badge-verified   { background:#d1fae5; color:#065f46; padding:3px 10px; border-radius:20px; font-weight:700; font-size:0.8rem; }
.badge-inaccurate { background:#fef3c7; color:#92400e; padding:3px 10px; border-radius:20px; font-weight:700; font-size:0.8rem; }
.badge-false      { background:#fee2e2; color:#991b1b; padding:3px 10px; border-radius:20px; font-weight:700; font-size:0.8rem; }
.badge-uncertain  { background:#e0e7ff; color:#3730a3; padding:3px 10px; border-radius:20px; font-weight:700; font-size:0.8rem; }
.claim-card { background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px; padding:1rem 1.2rem; margin-bottom:1rem; }
.claim-text { font-size:1rem; font-weight:600; color:#0f172a; margin-bottom:0.4rem; }
.verdict-text { font-size:0.9rem; color:#374151; margin-top:0.5rem; }
.source-link { font-size:0.8rem; color:#0891b2; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("## 🔍 FactCheck Agent")
st.markdown("*Upload a PDF — the AI extracts claims, searches the live web, and flags what's true, outdated, or false.*")
st.divider()

# ── Helpers ────────────────────────────────────────────────────────────────────
def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_claims(client: anthropic.Anthropic, text: str) -> list[dict]:
    prompt = f"""You are a claim-extraction engine.

From the document below, extract every verifiable factual claim: statistics, percentages,
dates, named figures, financial numbers, technical specifications, rankings, and quoted research.
Return ONLY a valid JSON array (no markdown, no commentary) with objects like:
{{"claim": "...", "category": "statistic|date|financial|technical|ranking|research"}}

Extract at least 8 claims if possible, up to 20.

DOCUMENT:
{text[:8000]}
"""
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    # Strip possible markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def verify_claim(client: anthropic.Anthropic, claim: str) -> dict:
    """Use Claude with web-search tool to fact-check a single claim."""
    prompt = f"""You are a professional fact-checker with access to live web search.

CLAIM TO VERIFY: "{claim}"

Steps:
1. Search the web for the most authoritative, current information on this claim.
2. Compare what you find with the claim.
3. Return ONLY a valid JSON object (no markdown) with these fields:
   - "verdict": one of "Verified", "Inaccurate", "False", "Uncertain"
   - "explanation": 1-2 sentence plain-English explanation of your finding
   - "real_fact": the correct/current fact if the claim is wrong (null if verified)
   - "sources": array of up to 2 source URLs you used (empty array if none found)

Verdict guide:
- Verified   → claim matches current data
- Inaccurate → claim was once true or is partially true but outdated/off
- False      → claim contradicts current evidence / no credible evidence found
- Uncertain  → conflicting sources, unable to determine definitively
"""
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=800,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{"role": "user", "content": prompt}],
    )
    # Gather all text blocks
    text_blocks = [b.text for b in response.content if hasattr(b, "text")]
    raw = "\n".join(text_blocks).strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw)
    raw = re.sub(r"\n?```$", "", raw)
    try:
        return json.loads(raw)
    except Exception:
        # Fallback
        return {
            "verdict": "Uncertain",
            "explanation": raw[:300] if raw else "Could not parse result.",
            "real_fact": None,
            "sources": [],
        }


BADGE = {
    "Verified":   '<span class="badge-verified">✅ VERIFIED</span>',
    "Inaccurate": '<span class="badge-inaccurate">⚠️ INACCURATE</span>',
    "False":      '<span class="badge-false">❌ FALSE</span>',
    "Uncertain":  '<span class="badge-uncertain">❓ UNCERTAIN</span>',
}

# ── API Key ────────────────────────────────────────────────────────────────────
api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...", help="Your key is never stored.")

# ── Upload ─────────────────────────────────────────────────────────────────────
uploaded = st.file_uploader("Upload PDF", type=["pdf"])

if uploaded and api_key:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run = st.button("🚀 Run Fact-Check")

    if run:
        try:
            client = anthropic.Anthropic(api_key=api_key)
        except Exception as e:
            st.error(f"Invalid API key: {e}")
            st.stop()

        # 1. Extract text
        with st.spinner("📄 Reading PDF…"):
            pdf_text = extract_text_from_pdf(uploaded.read())
            if len(pdf_text.strip()) < 50:
                st.error("Could not extract text from this PDF. Try a text-based PDF.")
                st.stop()

        st.success(f"✅ Extracted {len(pdf_text):,} characters from PDF")

        # 2. Extract claims
        with st.spinner("🧠 Extracting verifiable claims…"):
            try:
                claims = extract_claims(client, pdf_text)
            except Exception as e:
                st.error(f"Claim extraction failed: {e}")
                st.stop()

        st.info(f"🔎 Found **{len(claims)}** verifiable claims — verifying each against live web…")
        st.divider()

        # 3. Verify each claim
        results = []
        progress = st.progress(0)
        status_text = st.empty()

        for idx, item in enumerate(claims):
            claim_text = item.get("claim", "")
            category = item.get("category", "")
            status_text.markdown(f"*Checking claim {idx+1}/{len(claims)}: {claim_text[:80]}…*")

            try:
                verdict_data = verify_claim(client, claim_text)
            except Exception as e:
                verdict_data = {"verdict": "Uncertain", "explanation": str(e), "real_fact": None, "sources": []}

            results.append({**item, **verdict_data})
            progress.progress((idx + 1) / len(claims))
            time.sleep(0.3)  # polite rate limiting

        status_text.empty()
        progress.empty()

        # 4. Summary banner
        counts = {"Verified": 0, "Inaccurate": 0, "False": 0, "Uncertain": 0}
        for r in results:
            counts[r.get("verdict", "Uncertain")] += 1

        st.markdown("### 📊 Summary")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("✅ Verified",    counts["Verified"])
        c2.metric("⚠️ Inaccurate", counts["Inaccurate"])
        c3.metric("❌ False",       counts["False"])
        c4.metric("❓ Uncertain",   counts["Uncertain"])

        accuracy = counts["Verified"] / len(results) * 100 if results else 0
        risk = counts["False"] + counts["Inaccurate"]
        if risk == 0:
            st.success("🟢 No flagged claims — document appears factually sound.")
        elif risk <= 2:
            st.warning(f"🟡 {risk} claim(s) need attention.")
        else:
            st.error(f"🔴 {risk} claims are inaccurate or false — review before publishing!")

        st.divider()
        st.markdown("### 📋 Detailed Results")

        # Sort: False → Inaccurate → Uncertain → Verified
        order = {"False": 0, "Inaccurate": 1, "Uncertain": 2, "Verified": 3}
        results.sort(key=lambda r: order.get(r.get("verdict", "Uncertain"), 2))

        for r in results:
            verdict = r.get("verdict", "Uncertain")
            badge = BADGE.get(verdict, BADGE["Uncertain"])
            real_fact_html = ""
            if r.get("real_fact"):
                real_fact_html = f'<div style="background:#fef9c3;border-left:3px solid #f59e0b;padding:6px 10px;margin-top:6px;border-radius:4px;font-size:0.88rem;"><b>✏️ Real Fact:</b> {r["real_fact"]}</div>'
            sources_html = ""
            if r.get("sources"):
                links = " · ".join(f'<a href="{s}" target="_blank" class="source-link">{s[:60]}…</a>' if len(s) > 60 else f'<a href="{s}" target="_blank" class="source-link">{s}</a>' for s in r["sources"][:2])
                sources_html = f'<div style="margin-top:4px;">🔗 {links}</div>'

            st.markdown(f"""
<div class="claim-card">
  <div class="claim-text">"{r['claim']}"</div>
  <div style="margin-bottom:4px;">{badge} &nbsp; <span style="font-size:0.78rem;color:#6b7280;text-transform:uppercase;">{r.get('category','')}</span></div>
  <div class="verdict-text">{r.get('explanation','')}</div>
  {real_fact_html}
  {sources_html}
</div>
""", unsafe_allow_html=True)

        # 5. JSON download
        st.divider()
        st.download_button(
            "⬇️ Download Full Report (JSON)",
            data=json.dumps(results, indent=2),
            file_name="factcheck_report.json",
            mime="application/json",
        )

elif uploaded and not api_key:
    st.warning("⬆️ Please enter your Anthropic API key above to run the fact-check.")
elif not uploaded:
    st.info("⬆️ Upload a PDF to get started.")

st.divider()
st.caption("Built with Claude claude-sonnet-4-6 + Web Search · CogCulture Assessment 2025")
