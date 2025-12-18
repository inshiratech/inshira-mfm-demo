import streamlit as st
import pandas as pd

from mfm.synthetic import make_synthetic_bundle
from mfm.ai_assist import suggest_dataset_type, suggest_column_mapping, suggest_process_type
from mfm.model import build_flow_model, compute_balances, build_sankey_inputs
from mfm.viz import render_sankey, render_kpis, render_energy, render_circularity
from mfm.report import build_pdf_report

# ---------- Product-like styling ----------
st.set_page_config(page_title="Inshira • Material Flow Map (MVP)", layout="wide")

st.markdown("""
<style>
.block-container { padding-top: 1.2rem; }
.small-muted { color: #6b7280; font-size: 0.92rem; }
.card { border: 1px solid #e5e7eb; border-radius: 12px; padding: 14px 14px 10px 14px; background: white; }
.badge { display:inline-block; padding: 2px 8px; border-radius: 999px; background: #f3f4f6; font-size: 0.85rem; }
hr { margin: 1rem 0; }
</style>
""", unsafe_allow_html=True)

# ---------- Session state ----------
if "step" not in st.session_state:
    st.session_state.step = 1
if "process_blocks" not in st.session_state:
    st.session_state.process_blocks = []
if "bundle" not in st.session_state:
    st.session_state.bundle = None

def goto(step: int):
    st.session_state.step = step

# ---------- Header ----------
colH1, colH2 = st.columns([3, 1])
with colH1:
    st.markdown("## Inshira • Gate-to-Gate Material Flow Map (MVP)")
    st.markdown('<div class="small-muted">Build a lightweight virtual copy of processes using existing logs (no sensors). AI reduces manual mapping effort — physics stays explainable.</div>', unsafe_allow_html=True)
with colH2:
    st.markdown('<div class="card"><div class="badge">MVP Demo</div><br><span class="small-muted">Streamlit + synthetic data + human-in-the-loop AI</span></div>', unsafe_allow_html=True)

st.write("")

# ---------- Sidebar: navigation + scenarios ----------
with st.sidebar:
    st.markdown("### Navigation")
    step_labels = {
        1: "1) Scope",
        2: "2) Process map",
        3: "3) Data",
        4: "4) Results",
    }
    st.session_state.step = st.radio(
        "Go to",
        options=[1, 2, 3, 4],
        format_func=lambda x: step_labels[x],
        index=st.session_state.step - 1,
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown("### Demo settings")
    demo_mode = st.toggle("Use synthetic data", value=True, help="Turn off to upload your own CSV/XLSX.")

    st.divider()
    st.markdown("### Scenarios (What-if)")
    scrap_reduction_pct = st.slider("Scrap / waste reduction (%)", 0, 30, 0, 1)
    yield_improve_pct = st.slider("Yield improvement (%)", 0, 15, 0, 1)
    energy_intensity_improve_pct = st.slider("Energy intensity improvement (%)", 0, 20, 0, 1)
    allocate_energy = st.toggle("Allocate site energy to processes", value=False, help="Uses a proxy allocation for demo purposes.")

    scenarios = {
        "scrap_reduction_pct": float(scrap_reduction_pct),
        "yield_improve_pct": float(yield_improve_pct),
        "energy_intensity_improve_pct": float(energy_intensity_improve_pct),
        "allocate_energy": bool(allocate_energy),
    }

# ---------- STEP 1: Scope ----------
if st.session_state.step == 1:
    st.markdown("### 1) Scope")
    st.markdown('<div class="small-muted">Define the gate-to-gate boundary. Keep it simple for the first walkthrough.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([2, 2], gap="large")
    with c1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        site_name = st.text_input("Site name", value="SME Metal Fab Site")
        boundary_start = st.text_input("Start gate", value="Goods In (Raw Material)")
        boundary_end = st.text_input("End gate", value="Dispatch (Finished Goods)")
        time_period = st.selectbox("Time period", ["Quarter", "Month"], index=0)
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**What success looks like (MVP)**")
        st.write("• Map a core production flow in under **5 minutes**")
        st.write("• Upload (or use synthetic) **4 common datasets**")
        st.write("• Produce an explainable **Sankey flow map + hotspots**")
        st.write("• Generate a shareable **PDF report**")
        st.markdown("</div>", unsafe_allow_html=True)

    st.session_state.scope = {
        "site_name": site_name,
        "boundary_start": boundary_start,
        "boundary_end": boundary_end,
        "time_period": time_period,
    }

    st.write("")
    colN1, colN2 = st.columns([1, 5])
    with colN1:
        st.button("Next →", type="primary", use_container_width=True, on_click=goto, args=(2,))

# ---------- STEP 2: Process map ----------
elif st.session_state.step == 2:
    st.markdown("### 2) Process map")
    st.markdown('<div class="small-muted">Click to assemble a linear process flow. MVP keeps it linear (no loops) for speed and clarity.</div>', unsafe_allow_html=True)

    DEFAULT_LIBRARY = [
        "Material Intake", "Preparation", "Cutting", "Forming", "Welding / Joining",
        "Thermal Processing", "Surface Treatment", "Assembly", "Inspection", "Packaging & Dispatch", "Storage"
    ]

    left, right = st.columns([2, 3], gap="large")

    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Add blocks**")
        library = st.multiselect("Library", DEFAULT_LIBRARY, default=[
            "Material Intake", "Cutting", "Forming", "Welding / Joining", "Surface Treatment", "Assembly", "Packaging & Dispatch"
        ])

        add_block = st.selectbox("Select block to add", ["—"] + library)
        colB1, colB2 = st.columns(2)
        with colB1:
            if st.button("Add", use_container_width=True) and add_block != "—":
                st.session_state.process_blocks.append({
                    "name": add_block,
                    "user_label": add_block,
                    "type": suggest_process_type(add_block),
                    "yield_pct": 92,
                    "primary_material": "Mild steel sheet 2mm",
                    "throughput_unit": "kg",
                })
                st.toast("Block added", icon="✅")
        with colB2:
            if st.button("Undo", use_container_width=True) and st.session_state.process_blocks:
                st.session_state.process_blocks = st.session_state.process_blocks[:-1]
                st.toast("Removed last block", icon="↩️")

        st.write("")
        if st.session_state.process_blocks:
            st.markdown("**Current flow**")
            for i, b in enumerate(st.session_state.process_blocks, start=1):
                st.write(f"{i}. **{b['user_label']}**  ·  <span class='badge'>{b['type']}</span>", unsafe_allow_html=True)
        else:
            st.info("Add at least 3 blocks to proceed.")

        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Block details**  <span class='small-muted'>(optional but helps realism)</span>", unsafe_allow_html=True)

        if not st.session_state.process_blocks:
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            idx = st.number_input("Select block #", 1, len(st.session_state.process_blocks), 1, 1)
            block = st.session_state.process_blocks[idx - 1]

            block["user_label"] = st.text_input("Label", value=block["user_label"], key=f"label_{idx}")
            block["type"] = st.selectbox(
                "Process type",
                ["intake", "prep", "cutting", "forming", "joining", "thermal", "surface", "assembly", "inspection", "packaging", "storage", "other"],
                index=["intake","prep","cutting","forming","joining","thermal","surface","assembly","inspection","packaging","storage","other"].index(block["type"]),
                key=f"type_{idx}"
            )
            block["primary_material"] = st.text_input("Primary material", value=block.get("primary_material", ""), key=f"mat_{idx}")
            block["throughput_unit"] = st.selectbox("Throughput unit", ["kg", "pcs", "m2"], index=["kg","pcs","m2"].index(block.get("throughput_unit", "kg")), key=f"unit_{idx}")
            block["yield_pct"] = st.slider("Estimated yield (%)", 60, 100, int(block.get("yield_pct", 92)), 1, key=f"yield_{idx}")

            st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    nav1, nav2, nav3 = st.columns([1, 1, 6])
    with nav1:
        st.button("← Back", use_container_width=True, on_click=goto, args=(1,))
    with nav2:
        can_next = len(st.session_state.process_blocks) >= 3
        st.button("Next →", type="primary", disabled=not can_next, use_container_width=True, on_click=goto, args=(3,))
    if not can_next:
        st.caption("Add at least 3 process blocks to continue.")

# ---------- STEP 3: Data ----------
elif st.session_state.step == 3:
    st.markdown("### 3) Data")
    st.markdown('<div class="small-muted">Use synthetic data for a clean demo, or upload your own files. AI suggests dataset types and column mappings (you confirm).</div>', unsafe_allow_html=True)

    bundle = None

    if demo_mode:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.success("Synthetic data loaded (demo-ready).")
        bundle = make_synthetic_bundle()
        t1, t2, t3, t4 = st.tabs(["Production", "Materials", "Energy", "Waste"])
        t1.dataframe(bundle["production_output"], use_container_width=True)
        t2.dataframe(bundle["material_purchases"], use_container_width=True)
        t3.dataframe(bundle["energy_site"], use_container_width=True)
        t4.dataframe(bundle["waste_summary"], use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.info("Upload CSV/XLSX. Tip: start with production output + material purchases.")
        uploads = st.file_uploader("Upload files", type=["csv", "xlsx"], accept_multiple_files=True)

        parsed = []
        for f in uploads or []:
            if f.name.lower().endswith(".csv"):
                df = pd.read_csv(f)
            else:
                df = pd.read_excel(f)
            parsed.append((f.name, df))

        if parsed:
            bundle = {}
            for name, df in parsed:
                dtype = suggest_dataset_type(name, df)
                st.subheader(name)
                st.caption(f"AI suggestion: **{dtype}** (confirm)")
                dtype_confirm = st.selectbox(
                    f"Confirm type for {name}",
                    ["production_output", "material_purchases", "energy_site", "waste_summary"],
                    index=["production_output","material_purchases","energy_site","waste_summary"].index(dtype)
                )
                mapping = suggest_column_mapping(dtype_confirm, df)
                st.write("AI column mapping suggestion:")
                st.json(mapping)
                bundle[dtype_confirm] = df
                st.dataframe(df.head(20), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    if bundle is None:
        st.warning("No data available yet.")
    else:
        st.session_state.bundle = bundle
        st.toast("Data ready", icon="📦")

    st.write("")
    nav1, nav2, nav3 = st.columns([1, 1, 6])
    with nav1:
        st.button("← Back", use_container_width=True, on_click=goto, args=(2,))
    with nav2:
        can_next = st.session_state.bundle is not None
        st.button("Next →", type="primary", disabled=not can_next, use_container_width=True, on_click=goto, args=(4,))
    if not can_next:
        st.caption("Load synthetic data or upload at least one dataset to continue.")

# ---------- STEP 4: Results ----------
else:
    st.markdown("### 4) Results")
    st.markdown('<div class="small-muted">Results update live with scenarios. Export a PDF for sharing.</div>', unsafe_allow_html=True)

    scope = st.session_state.get("scope", {
        "site_name": "Site",
        "boundary_start": "Start",
        "boundary_end": "End",
        "time_period": "Quarter",
    })

    if not st.session_state.process_blocks or st.session_state.bundle is None:
        st.error("Missing process map or data. Go back to Steps 2–3.")
        st.stop()

    model = build_flow_model(
        site_name=scope["site_name"],
        boundary_start=scope["boundary_start"],
        boundary_end=scope["boundary_end"],
        process_blocks=st.session_state.process_blocks,
        data_bundle=st.session_state.bundle,
        time_period=scope["time_period"],
        scenarios=scenarios,
    )

    results = compute_balances(model)
    sankey = build_sankey_inputs(results)

    left, right = st.columns([2, 1], gap="large")
    with left:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Material Flow Map**")
        fig = render_sankey(sankey, title=f"{scope['site_name']} — {scope['boundary_start']} → {scope['boundary_end']}")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**KPIs**")
        render_kpis(results)

        st.write("")
        st.markdown("**AI assist highlights**")
        if results["ai_messages"]:
            for msg in results["ai_messages"]:
                st.write(f"• {msg}")
        else:
            st.write("• None yet — try scenario sliders or add more detailed data.")

        st.write("")
        st.markdown("**Assumptions & data gaps**")
        for a in results["assumptions"]:
            st.write(f"• {a}")

        st.write("")
        pdf_bytes = build_pdf_report(
            site_name=scope["site_name"],
            boundary_start=scope["boundary_start"],
            boundary_end=scope["boundary_end"],
            results=results,
            sankey_fig=fig,  # will embed image if kaleido works
        )
        st.download_button(
            "⬇️ Download PDF report",
            data=pdf_bytes,
            file_name="material_flow_map_report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    tab1, tab2, tab3 = st.tabs(["Energy", "Circular economy", "Transparency"])
    with tab1:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Energy usage & intensity**")
        render_energy(results)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab2:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Circular economy view**")
        render_circularity(results)
        st.markdown("</div>", unsafe_allow_html=True)

    with tab3:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("**Computed flows (explainable)**")
        st.dataframe(results["flows_table"], use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    nav1, nav2 = st.columns([1, 6])
    with nav1:
        st.button("← Back", use_container_width=True, on_click=goto, args=(3,))
