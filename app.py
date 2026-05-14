"""
Phase 4: Streamlit Frontend — Drug Brochure Generator
"""

import streamlit as st
import base64
import time
from fetcher import fetch_drug_data
from brochure import generate_brochure

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="MedicoGen — Drug Brochure Generator",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:wght@300;400;500;600&display=swap');

/* ── Root tokens ── */
:root {
    --navy:      #1B3A6B;
    --teal:      #0D7E83;
    --teal-lt:   #D6EEEF;
    --amber:     #E8A020;
    --bg:        #F4F7FB;
    --card:      #FFFFFF;
    --text:      #1E1E1E;
    --muted:     #6B7280;
    --border:    #DDE3EC;
    --radius:    12px;
    --shadow:    0 4px 24px rgba(27,58,107,0.10);
}

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
    background: var(--bg) !important;
    color: var(--text);
}

/* Hide default streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 2rem 3rem 2rem !important; max-width: 1100px !important; }

/* ── Top hero banner ── */
.hero {
    background: linear-gradient(135deg, var(--navy) 0%, #0D4F7C 60%, var(--teal) 100%);
    border-radius: 0 0 28px 28px;
    padding: 2.8rem 3rem 2.4rem;
    margin: 0 -2rem 2.5rem -2rem;
    position: relative;
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 260px; height: 260px;
    background: rgba(13,126,131,0.25);
    border-radius: 50%;
}
.hero::after {
    content: '';
    position: absolute;
    bottom: -40px; left: 40px;
    width: 140px; height: 140px;
    background: rgba(232,160,32,0.15);
    border-radius: 50%;
}
.hero-eyebrow {
    font-family: 'DM Sans', sans-serif;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.18em;
    color: var(--amber);
    text-transform: uppercase;
    margin-bottom: 0.5rem;
}
.hero-title {
    font-family: 'DM Serif Display', serif;
    font-size: 2.6rem;
    color: #FFFFFF;
    line-height: 1.15;
    margin: 0 0 0.6rem 0;
}
.hero-sub {
    font-size: 1rem;
    color: rgba(255,255,255,0.72);
    font-weight: 300;
    max-width: 520px;
    line-height: 1.6;
}
.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 20px;
    padding: 0.25rem 0.85rem;
    font-size: 0.75rem;
    color: rgba(255,255,255,0.85);
    margin-top: 1.2rem;
    backdrop-filter: blur(4px);
}

/* ── Search card ── */
.search-card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem 2rem 1.6rem;
    box-shadow: var(--shadow);
    margin-bottom: 2rem;
}
.search-label {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: var(--navy);
    margin-bottom: 0.5rem;
}

/* ── Streamlit input override ── */
.stTextInput > div > div > input {
    border: 1.5px solid var(--border) !important;
    border-radius: 8px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 1rem !important;
    padding: 0.65rem 1rem !important;
    color: var(--text) !important;
    background: #FAFBFC !important;
    transition: border-color 0.2s;
}
.stTextInput > div > div > input:focus {
    border-color: var(--teal) !important;
    box-shadow: 0 0 0 3px rgba(13,126,131,0.12) !important;
}

/* ── Generate button ── */
.stButton > button {
    background: linear-gradient(135deg, var(--teal), #0A6469) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.65rem 2rem !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.95rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.02em !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 4px 14px rgba(13,126,131,0.35) !important;
    width: 100%;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 20px rgba(13,126,131,0.45) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}

/* ── Drug info summary cards ── */
.info-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.info-tile {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    box-shadow: 0 2px 8px rgba(27,58,107,0.06);
}
.info-tile-label {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--teal);
    margin-bottom: 0.3rem;
}
.info-tile-value {
    font-size: 0.95rem;
    font-weight: 500;
    color: var(--navy);
    line-height: 1.35;
}

/* ── Section heading ── */
.section-heading {
    font-family: 'DM Serif Display', serif;
    font-size: 1.3rem;
    color: var(--navy);
    margin: 1.8rem 0 1rem 0;
    display: flex;
    align-items: center;
    gap: 0.6rem;
}
.section-heading::after {
    content: '';
    flex: 1;
    height: 1px;
    background: var(--border);
}

/* ── PDF viewer container ── */
.pdf-container {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.2rem;
    box-shadow: var(--shadow);
}

/* ── Download button ── */
.download-btn {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    background: var(--navy);
    color: white !important;
    text-decoration: none !important;
    border-radius: 8px;
    padding: 0.65rem 1.6rem;
    font-family: 'DM Sans', sans-serif;
    font-size: 0.9rem;
    font-weight: 600;
    box-shadow: 0 4px 14px rgba(27,58,107,0.3);
    transition: all 0.2s;
}
.download-btn:hover {
    background: #152E56;
    transform: translateY(-1px);
    box-shadow: 0 6px 20px rgba(27,58,107,0.4);
}

/* ── Status / alert pills ── */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.4rem 1rem;
    border-radius: 20px;
    font-size: 0.82rem;
    font-weight: 500;
}
.status-success { background: #D1FAE5; color: #065F46; }
.status-error   { background: #FEE2E2; color: #991B1B; }
.status-info    { background: var(--teal-lt); color: var(--navy); }

/* ── Spinner override ── */
.stSpinner > div { border-top-color: var(--teal) !important; }

/* ── Quick-search chips ── */
.chip-row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.8rem; }
.chip {
    background: var(--teal-lt);
    color: var(--navy);
    border: 1px solid rgba(13,126,131,0.2);
    border-radius: 20px;
    padding: 0.25rem 0.85rem;
    font-size: 0.78rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
}

/* ── Progress steps ── */
.steps { display: flex; gap: 0; margin: 1rem 0; }
.step {
    flex: 1;
    text-align: center;
    padding: 0.5rem 0.3rem;
    font-size: 0.75rem;
    font-weight: 500;
    color: var(--muted);
    border-bottom: 2px solid var(--border);
    position: relative;
}
.step.active {
    color: var(--teal);
    border-bottom-color: var(--teal);
}
.step.done {
    color: var(--navy);
    border-bottom-color: var(--navy);
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: var(--navy) !important;
}
[data-testid="stSidebar"] * { color: rgba(255,255,255,0.85) !important; }
</style>
""", unsafe_allow_html=True)


# ── Helper: PDF → base64 embed ─────────────────────────────────────────────────
def pdf_to_base64(pdf_bytes: bytes) -> str:
    return base64.b64encode(pdf_bytes).decode("utf-8")


def render_pdf_embed(pdf_bytes: bytes, height: int = 620):
    b64 = pdf_to_base64(pdf_bytes)
    st.markdown(f"""
        <div class="pdf-container">
            <iframe
                src="data:application/pdf;base64,{b64}"
                width="100%" height="{height}px"
                style="border:none; border-radius:8px;"
            ></iframe>
        </div>
    """, unsafe_allow_html=True)


def download_button_html(pdf_bytes: bytes, filename: str) -> str:
    b64 = pdf_to_base64(pdf_bytes)
    return f"""
        <a class="download-btn"
           href="data:application/pdf;base64,{b64}"
           download="{filename}">
            ⬇ Download Brochure PDF
        </a>
    """


# ── Hero ───────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
    <div class="hero-eyebrow">Medico-Marketing Suite</div>
    <div class="hero-title">Drug Brochure<br>Generator</div>
    <div class="hero-sub">
        Enter any drug name and instantly generate a professional,
        print-ready tri-fold prescribing brochure — powered by FDA data.
    </div>
    <div class="hero-badge">🔬 Powered by OpenFDA &nbsp;·&nbsp; RxNorm &nbsp;·&nbsp; ReportLab</div>
</div>
""", unsafe_allow_html=True)


# ── Session state ──────────────────────────────────────────────────────────────
if "pdf_bytes"  not in st.session_state: st.session_state.pdf_bytes  = None
if "drug_data"  not in st.session_state: st.session_state.drug_data  = None
if "drug_input" not in st.session_state: st.session_state.drug_input = ""


# ── Search card ────────────────────────────────────────────────────────────────
st.markdown('<div class="search-card">', unsafe_allow_html=True)
st.markdown('<div class="search-label">Enter Drug Name</div>', unsafe_allow_html=True)

col_input, col_btn = st.columns([4, 1])
with col_input:
    drug_name = st.text_input(
        label="drug",
        placeholder="e.g. Metformin, Lisinopril, Atorvastatin...",
        label_visibility="collapsed",
        key="drug_input_field",
    )
with col_btn:
    st.markdown("<div style='height:0.1rem'></div>", unsafe_allow_html=True)
    generate = st.button("Generate Brochure", use_container_width=True)

# Quick-search chips
st.markdown("""
<div class="chip-row">
    <span class="chip">💊 Metformin</span>
    <span class="chip">💊 Lisinopril</span>
    <span class="chip">💊 Atorvastatin</span>
    <span class="chip">💊 Amlodipine</span>
    <span class="chip">💊 Omeprazole</span>
    <span class="chip">💊 Sertraline</span>
</div>
""", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# ── Generation pipeline ────────────────────────────────────────────────────────
if generate and drug_name.strip():

    # Progress steps UI
    steps_placeholder = st.empty()
    def show_step(active: int):
        labels = ["Fetching FDA Data", "Enriching via RxNorm", "Generating PDF", "Ready"]
        html = '<div class="steps">'
        for i, lbl in enumerate(labels):
            cls = "done" if i < active else ("active" if i == active else "step")
            html += f'<div class="step {cls}">{"✓ " if i < active else ""}{lbl}</div>'
        html += "</div>"
        steps_placeholder.markdown(html, unsafe_allow_html=True)

    show_step(0)
    status = st.empty()

    with st.spinner(""):
        # Step 1 — fetch
        status.markdown('<div class="status-pill status-info">🔍 Querying OpenFDA & RxNorm databases...</div>', unsafe_allow_html=True)
        show_step(0)
        data = fetch_drug_data(drug_name.strip())

        if "error" in data:
            steps_placeholder.empty()
            status.markdown(f'<div class="status-pill status-error">❌ {data["error"]}</div>', unsafe_allow_html=True)
            st.stop()

        show_step(1)
        time.sleep(0.3)

        # Step 2 — generate PDF
        status.markdown('<div class="status-pill status-info">🖨 Composing brochure layout...</div>', unsafe_allow_html=True)
        show_step(2)
        pdf_bytes = generate_brochure(data)

        # Store in session
        st.session_state.pdf_bytes = pdf_bytes
        st.session_state.drug_data = data

        show_step(3)
        status.markdown('<div class="status-pill status-success">✅ Brochure ready!</div>', unsafe_allow_html=True)
        time.sleep(0.4)
        status.empty()
        steps_placeholder.empty()


elif generate and not drug_name.strip():
    st.markdown('<div class="status-pill status-error">⚠️ Please enter a drug name first.</div>', unsafe_allow_html=True)


# ── Results ────────────────────────────────────────────────────────────────────
if st.session_state.pdf_bytes and st.session_state.drug_data:
    data = st.session_state.drug_data
    pdf  = st.session_state.pdf_bytes

    # ── Drug summary tiles ────────────────────────────────────────────────────
    st.markdown('<div class="section-heading">Drug Summary</div>', unsafe_allow_html=True)

    brands_str = ", ".join(data.get("brand_names", [])[:3]) or "—"
    st.markdown(f"""
    <div class="info-grid">
        <div class="info-tile">
            <div class="info-tile-label">Generic Name</div>
            <div class="info-tile-value">{data.get("generic_name","—").title()}</div>
        </div>
        <div class="info-tile">
            <div class="info-tile-label">Brand Names</div>
            <div class="info-tile-value">{brands_str}</div>
        </div>
        <div class="info-tile">
            <div class="info-tile-label">Drug Class</div>
            <div class="info-tile-value">{data.get("drug_class","—")}</div>
        </div>
        <div class="info-tile">
            <div class="info-tile-label">Manufacturer</div>
            <div class="info-tile-value">{data.get("manufacturer","—")[:50]}</div>
        </div>
        <div class="info-tile">
            <div class="info-tile-label">Route</div>
            <div class="info-tile-value">Oral</div>
        </div>
        <div class="info-tile">
            <div class="info-tile-label">Rx Status</div>
            <div class="info-tile-value">Prescription Only</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── PDF preview + download ────────────────────────────────────────────────
    st.markdown('<div class="section-heading">Brochure Preview</div>', unsafe_allow_html=True)

    dl_col, _ = st.columns([2, 5])
    with dl_col:
        filename = f"{data.get('drug_name','drug').replace(' ','_')}_brochure.pdf"
        st.markdown(download_button_html(pdf, filename), unsafe_allow_html=True)

    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    render_pdf_embed(pdf, height=640)

    # ── Expandable raw sections ───────────────────────────────────────────────
    st.markdown('<div class="section-heading">Raw FDA Data</div>', unsafe_allow_html=True)

    fields = [
        ("Indications & Usage",     "indications"),
        ("Dosage & Administration", "dosage"),
        ("Contraindications",       "contraindications"),
        ("Warnings & Precautions",  "warnings"),
        ("Adverse Reactions",       "adverse_reactions"),
        ("How Supplied",            "how_supplied"),
        ("Storage & Handling",      "storage"),
    ]
    for label, key in fields:
        with st.expander(label):
            st.write(data.get(key, "Not available."))


# ── Empty state ────────────────────────────────────────────────────────────────
else:
    st.markdown("""
    <div style="text-align:center; padding: 3rem 2rem; color: #9CA3AF;">
        <div style="font-size:3rem; margin-bottom:1rem;">💊</div>
        <div style="font-family:'DM Serif Display',serif; font-size:1.4rem;
                    color:#1B3A6B; margin-bottom:0.5rem;">
            Ready to generate your brochure
        </div>
        <div style="font-size:0.9rem; max-width:380px; margin:0 auto; line-height:1.6;">
            Type any drug name above and click <strong>Generate Brochure</strong>
            to produce a professional tri-fold prescribing information brochure.
        </div>
    </div>
    """, unsafe_allow_html=True)
