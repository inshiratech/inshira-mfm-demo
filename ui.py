import streamlit as st
import base64
from pathlib import Path

CSS = """
<style>
:root{
  --bg: #ffffff;
  --surface: #f6f7fb;
  --card: rgba(255,255,255,.9);
  --border: rgba(15,23,42,.10);
  --shadow: 0 10px 30px rgba(2,6,23,.08);
  --shadow-sm: 0 6px 16px rgba(2,6,23,.06);
  --text: #0b1220;
  --muted: rgba(11,18,32,.62);
  --brand: #0b1220;
  --brand2: #3b82f6;
  --ok: #16a34a;
  --warn: #f59e0b;
  --bad: #ef4444;
  --radius: 16px;
}

.block-container { padding-top: 1.1rem; padding-bottom: 2rem; max-width: 1200px; }
section[data-testid="stSidebar"] { border-right: 1px solid var(--border); }

h1,h2,h3 { letter-spacing: -0.02em; }
.small { color: var(--muted); font-size: .95rem; line-height: 1.4; }
.kicker { color: var(--muted); font-size: .9rem; text-transform: uppercase; letter-spacing: .08em; }

.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 16px 12px 16px;
  box-shadow: var(--shadow-sm);
}

.hero {
  border-radius: 22px;
  padding: 22px 22px 18px 22px;
  border: 1px solid var(--border);
  background: linear-gradient(135deg, rgba(59,130,246,.10), rgba(16,185,129,.08) 45%, rgba(255,255,255,1) 100%);
  box-shadow: var(--shadow);
}

.badge {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.7);
  font-size: .85rem;
  color: rgba(11,18,32,.74);
}

.pill {
  display:inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  background: rgba(15,23,42,.06);
  border: 1px solid var(--border);
  font-size: .82rem;
  color: rgba(11,18,32,.7);
}

.divider {
  height: 1px; background: var(--border);
  margin: 12px 0 14px 0;
}

.stButton>button, .stDownloadButton>button {
  border-radius: 12px !important;
  padding: 10px 12px !important;
  font-weight: 600 !important;
  border: 1px solid var(--border) !important;
}

.stButton>button[kind="primary"]{
  background: var(--brand) !important;
  color: white !important;
}

.metric-row {
  display:grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.metric {
  border: 1px solid var(--border);
  background: rgba(255,255,255,.7);
  border-radius: 14px;
  padding: 12px 12px 10px 12px;
}
.metric .label { color: var(--muted); font-size: .85rem; }
.metric .value { font-size: 1.25rem; font-weight: 750; letter-spacing: -0.02em; }

.stepper {
  display:flex; gap: 10px; flex-wrap: wrap;
  margin-top: 10px;
}
.step {
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: rgba(255,255,255,.65);
  color: rgba(11,18,32,.75);
  font-size: .9rem;
}
.step.active{
  background: rgba(15,23,42,.92);
  color: white;
  border-color: rgba(15,23,42,.92);
}
</style>
"""
def img_to_data_uri(path: str) -> str:
    p = Path(path)
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode("utf-8")
    ext = p.suffix.lower().lstrip(".")
    mime = "png" if ext == "png" else ext
    return f"data:image/{mime};base64,{b64}"

def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)

def card(title: str, subtitle: str | None = None, icon: str = "✨"):
    st.markdown(f"""
<div class="card">
  <div class="badge">{icon} <b>{title}</b></div>
  {"<div class='small' style='margin-top:8px'>" + subtitle + "</div>" if subtitle else ""}
</div>
""", unsafe_allow_html=True)

def hero(title: str, subtitle: str, right_badge: str = "MVP"):
    st.markdown(f"""
<div class="hero">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; gap: 14px;">
    <div>
      <div class="kicker">Inshira • Material Flow Mapping</div>
      <div style="font-size:1.75rem; font-weight:800; letter-spacing:-0.03em; margin-top:6px">{title}</div>
      <div class="small" style="margin-top:8px">{subtitle}</div>
      <div class="stepper">
        <div class="step">Scope</div>
        <div class="step">Process</div>
        <div class="step">Data</div>
        <div class="step">Insights</div>
      </div>
    </div>
    <div class="badge">✅ {right_badge}</div>
  </div>
</div>
""", unsafe_allow_html=True)

def stepper(active_idx: int):
    labels = ["1 Scope", "2 Process", "3 Data", "4 Insights"]
    pills = []
    for i, lab in enumerate(labels, start=1):
        cls = "step active" if i == active_idx else "step"
        pills.append(f"<div class='{cls}'>{lab}</div>")
    st.markdown(f"<div class='stepper'>{''.join(pills)}</div>", unsafe_allow_html=True)

def metric_pair(label1, value1, label2, value2):
    st.markdown(f"""
<div class="metric-row">
  <div class="metric"><div class="label">{label1}</div><div class="value">{value1}</div></div>
  <div class="metric"><div class="label">{label2}</div><div class="value">{value2}</div></div>
</div>
""", unsafe_allow_html=True)
