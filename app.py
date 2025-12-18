import streamlit as st
import pandas as pd

from ui import inject_css, hero, stepper, metric_pair
from mfm.synthetic import make_synthetic_bundle
from mfm.ai_assist import suggest_dataset_type, suggest_column_mapping, suggest_process_type
from mfm.model import build_flow_model, compute_balances, build_sankey_inputs
from mfm.viz import render_sankey, render_energy, render_circularity
from mfm.report import build_pdf_report

st.set_page_config(page_title="Inshira • Material Flow Mapping", layout="wide")
inject_css()

# ---------- state ----------
if "step" not in st.session_state: st.session_state.step = 1
if "scope" not in st.session_state:
    st.session_state.scope = {
        "site_name":"SME Metal Fab Site",
        "boundary_start":"Goods In (Raw Material)",
        "boundary_end":"Dispatch (Finished Goods)",
        "time_period":"Quarter"
    }
if "process_blocks" not in st.session_state: st.session_state.process_blocks = []
if "bundle" not in st.session_state: st.session_state.bundle = None

def goto(n: int): st.session_state.step = n

# ---------- sidebar ----------
with st.sidebar:
    st.markdown("### Workspace")
    st.caption("A guided, explainable material + energy baseline. No sensors needed.")

    st.session_state.step = st.radio(
        "Navigate",
        options=[1,2,3,4],
        format_func=lambda x: ["Scope","Process map","Data","Insights"][x-1],
        index=st.session_state.step-1,
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown("### Scenarios")
    scrap_reduction = st.slider("Scrap / waste reduction (%)", 0, 30, 0, 1)
    yield_improve = st.slider("Yield improvement (%)", 0, 15, 0, 1)
    energy_improve = st.slider("Energy intensity improvement (%)", 0, 20, 0, 1)
    allocate_energy = st.toggle("Allocate site energy to processes", value=False)

    scenarios = {
        "scrap_reduction_pct": float(scrap_reduction),
        "yield_improve_pct": float(yield_improve),
        "energy_intensity_improve_pct": float(energy_improve),
        "allocate_energy": bool(allocate_energy),
    }

    st.markdown("---")
    demo_mode = st.toggle("Demo mode (synthetic data)", value=True)

# ---------- top hero ----------
hero(
    title="Gate-to-Gate Material Flow Map",
    subtitle="Create a virtual copy of shop-floor processes using existing logs (production, materials, energy, waste). AI assists with messy inputs; the model remains physics-first and explainable.",
    right_badge="Demo-ready"
)
stepper(st.session_state.step)
st.write("")

# ---------- STEP 1 ----------
if st.session_state.step == 1:
    c1, c2 = st.columns([2, 1], gap="large")
    with c1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Define scope**  \n<span class='small'>This sets the gate-to-gate boundary used throughout reports and exports.</span>", unsafe_allow_html=True)
        scope = st.session_state.scope
        scope["site_name"] = st.text_input("Site name", value=scope["site_name"])
        scope["boundary_start"] = st.text_input("Start gate", value=scope["boundary_start"])
        scope["boundary_end"] = st.text_input("End gate", value=scope["boundary_end"])
        scope["time_period"] = st.selectbox("Time period", ["Quarter","Month"], index=0 if scope["time_period"]=="Quarter" else 1)
        st.session_state.scope = scope
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**What you’ll get**  \n<span class='small'>In a few minutes:</span>", unsafe_allow_html=True)
        st.write("• Material flow Sankey")
        st.write("• Energy intensity + hotspots")
        st.write("• Circularity view (waste routes)")
        st.write("• PDF export for sharing")
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        st.button("Continue →", type="primary", use_container_width=True, on_click=goto, args=(2,))
        st.markdown("</div>", unsafe_allow_html=True)

# ---------- STEP 2 ----------
elif st.session_state.step == 2:
    DEFAULT_LIBRARY = [
        "Material Intake","Preparation","Cutting","Forming","Welding / Joining",
        "Thermal Processing","Surface Treatment","Assembly","Inspection","Packaging & Dispatch","Storage"
    ]

    left, right = st.columns([1.2, 1.8], gap="large")

    with left:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Build your process map**  \n<span class='small'>Add blocks in order. MVP keeps it linear for clarity.</span>", unsafe_allow_html=True)

        library = st.multiselect("Block library", DEFAULT_LIBRARY, default=[
            "Material Intake","Cutting","Forming","Welding / Joining","Surface Treatment","Assembly","Packaging & Dispatch"
        ])
        add_block = st.selectbox("Add a block", ["—"] + library)
        a,b = st.columns(2)
        with a:
            if st.button("Add", use_container_width=True) and add_block != "—":
                st.session_state.process_blocks.append({
                    "name": add_block,
                    "user_label": add_block,
                    "type": suggest_process_type(add_block),
                    "yield_pct": 92,
                    "primary_material": "Mild steel sheet 2mm",
                    "throughput_unit": "kg",
                })
                st.toast("Added block", icon="✅")
        with b:
            if st.button("Undo", use_container_width=True) and st.session_state.process_blocks:
                st.session_state.process_blocks = st.session_state.process_blocks[:-1]
                st.toast("Removed last block", icon="↩️")

        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)

        if not st.session_state.process_blocks:
            st.info("Add at least 3 blocks to continue.")
        else:
            st.markdown("**Current flow**")
            for i, blk in enumerate(st.session_state.process_blocks, start=1):
                st.write(f"{i}. **{blk['user_label']}**  ·  <span class='pill'>{blk['type']}</span>", unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Block settings**  \n<span class='small'>Optional — improves realism and energy allocation assumptions.</span>", unsafe_allow_html=True)

        if st.session_state.process_blocks:
            idx = st.number_input("Select block", 1, len(st.session_state.process_blocks), 1, 1)
            blk = st.session_state.process_blocks[idx-1]
            blk["user_label"] = st.text_input("Label", value=blk["user_label"], key=f"lbl_{idx}")
            blk["type"] = st.selectbox("Process type",
                ["intake","prep","cutting","forming","joining","thermal","surface","assembly","inspection","packaging","storage","other"],
                index=["intake","prep","cutting","forming","joining","thermal","surface","assembly","inspection","packaging","storage","other"].index(blk["type"]),
                key=f"typ_{idx}"
            )
            blk["primary_material"] = st.text_input("Primary material", value=blk.get("primary_material",""), key=f"mat_{idx}")
            blk["throughput_unit"] = st.selectbox("Throughput unit", ["kg","pcs","m2"], index=["kg","pcs","m2"].index(blk.get("throughput_unit","kg")), key=f"unit_{idx}")
            blk["yield_pct"] = st.slider("Estimated yield (%)", 60, 100, int(blk.get("yield_pct",92)), 1, key=f"y_{idx}")
        else:
            st.write("Add blocks on the left to edit settings.")

        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        nav1, nav2 = st.columns(2)
        with nav1:
            st.button("← Back", use_container_width=True, on_click=goto, args=(1,))
        with nav2:
            st.button("Continue →", type="primary", use_container_width=True, disabled=len(st.session_state.process_blocks)<3, on_click=goto, args=(3,))
        st.markdown("</div>", unsafe_allow_html=True)

# ---------- STEP 3 ----------
elif st.session_state.step == 3:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("**Add data**  \n<span class='small'>Use demo data for presentations, or upload CSV/XLSX. AI suggests dataset type + column mapping for confirmation.</span>", unsafe_allow_html=True)

    if demo_mode:
        bundle = make_synthetic_bundle()
        st.session_state.bundle = bundle
        t1,t2,t3,t4 = st.tabs(["Production","Materials","Energy","Waste"])
        t1.dataframe(bundle["production_output"], use_container_width=True)
        t2.dataframe(bundle["material_purchases"], use_container_width=True)
        t3.dataframe(bundle["energy_site"], use_container_width=True)
        t4.dataframe(bundle["waste_summary"], use_container_width=True)
    else:
        uploads = st.file_uploader("Upload files", type=["csv","xlsx"], accept_multiple_files=True)
        parsed = []
        for f in uploads or []:
            df = pd.read_csv(f) if f.name.lower().endswith(".csv") else pd.read_excel(f)
            parsed.append((f.name, df))

        if parsed:
            bundle = {}
            for name, df in parsed:
                dtype = suggest_dataset_type(name, df)
                st.subheader(name)
                st.caption(f"AI suggests: {dtype}")
                dtype_confirm = st.selectbox(f"Confirm type for {name}",
                    ["production_output","material_purchases","energy_site","waste_summary"],
                    index=["production_output","material_purchases","energy_site","waste_summary"].index(dtype)
                )
                mapping = suggest_column_mapping(dtype_confirm, df)
                st.caption("AI column mapping suggestion (you can adjust later):")
                st.json(mapping)
                bundle[dtype_confirm] = df
                st.dataframe(df.head(15), use_container_width=True)
            st.session_state.bundle = bundle
        else:
            st.info("Upload at least one file to continue.")

    st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
    nav1, nav2 = st.columns(2)
    with nav1:
        st.button("← Back", use_container_width=True, on_click=goto, args=(2,))
    with nav2:
        st.button("Continue →", type="primary", use_container_width=True, disabled=st.session_state.bundle is None, on_click=goto, args=(4,))
    st.markdown("</div>", unsafe_allow_html=True)

# ---------- STEP 4 ----------
else:
    scope = st.session_state.scope
    if not st.session_state.bundle or not st.session_state.process_blocks:
        st.error("Missing process map or data. Go back to previous steps.")
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

    top = st.columns([2.1, 1], gap="large")
    with top[0]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Material flow map**")
        fig = render_sankey(sankey, title=f"{scope['site_name']} — {scope['boundary_start']} → {scope['boundary_end']}")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with top[1]:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Highlights**  \n<span class='small'>Live-updating with scenarios.</span>", unsafe_allow_html=True)

        metric_pair("Material in (kg)", f"{results['mat_in_kg']:,.0f}",
                    "Product out (kg)", f"{results['prod_out_kg']:,.0f}")
        st.write("")
        metric_pair("Waste out (kg)", f"{results['waste_out_kg']:,.0f}",
                    "Efficiency (%)", f"{results['material_eff_pct']:.1f}")

        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        st.markdown("**AI assist**")
        if results.get("ai_messages"):
            for m in results["ai_messages"][:4]:
                st.write(f"• {m}")
        else:
            st.write("• No flags yet — try changing scenarios.")

        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        pdf = build_pdf_report(scope["site_name"], scope["boundary_start"], scope["boundary_end"], results, sankey_fig=fig)
        st.download_button("⬇️ Download report (PDF)", data=pdf, file_name="inshira_material_flow_report.pdf", mime="application/pdf", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    t1, t2, t3 = st.tabs(["Energy", "Circular economy", "Assumptions & transparency"])
    with t1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Energy usage**")
        render_energy(results)
        st.markdown("</div>", unsafe_allow_html=True)

    with t2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Circular economy**")
        render_circularity(results)
        st.markdown("</div>", unsafe_allow_html=True)

    with t3:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown("**Assumptions & data gaps**")
        for a in results.get("assumptions", []):
            st.write(f"• {a}")
        st.markdown("<div class='divider'></div>", unsafe_allow_html=True)
        st.markdown("**Computed flows**")
        st.dataframe(results["flows_table"], use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    st.write("")
    st.button("← Back to data", on_click=goto, args=(3,))
