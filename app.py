import streamlit as st
import pandas as pd

from mfm.synthetic import make_synthetic_bundle
from mfm.ai_assist import suggest_dataset_type, suggest_column_mapping, suggest_process_type
from mfm.model import build_flow_model, compute_balances, build_sankey_inputs
from mfm.viz import render_sankey, render_kpis, render_energy, render_circularity

st.set_page_config(page_title="Gate-to-Gate Material Flow Map (MVP Demo)", layout="wide")

st.title("Gate-to-Gate Material Flow Map — MVP Demo")
st.caption("No sensors. Uses existing logs/bills/waste reports. AI helps interpret messy data (human-in-the-loop).")

# -----------------------------
# Sidebar: Demo controls + scenarios
# -----------------------------
with st.sidebar:
    st.header("Demo Controls")
    demo_mode = st.toggle("Demo mode (use synthetic data)", value=True)

    st.divider()
    st.subheader("Factory scope")
    site_name = st.text_input("Site name", value="SME Metal Fab Site")
    boundary_start = st.text_input("Start gate", value="Goods In (Raw Material)")
    boundary_end = st.text_input("End gate", value="Dispatch (Finished Goods)")
    time_period = st.selectbox("Time period", ["Quarter", "Month"], index=0)

    st.divider()
    st.subheader("Scenarios (What-if)")
    scrap_reduction_pct = st.slider("Scrap / waste reduction (%)", 0, 30, 0, 1)
    yield_improve_pct = st.slider("Yield improvement (%)", 0, 15, 0, 1)
    energy_intensity_improve_pct = st.slider("Energy intensity improvement (%)", 0, 20, 0, 1)
    allocate_energy = st.toggle("Allocate site energy to processes (proxy)", value=False)

    scenarios = {
        "scrap_reduction_pct": float(scrap_reduction_pct),
        "yield_improve_pct": float(yield_improve_pct),
        "energy_intensity_improve_pct": float(energy_intensity_improve_pct),
        "allocate_energy": bool(allocate_energy),
    }

st.divider()

# -----------------------------
# Step 1: Click-based process map
# -----------------------------
st.header("1) Build the process map (click-based)")

DEFAULT_LIBRARY = [
    "Material Intake",
    "Preparation",
    "Cutting",
    "Forming",
    "Welding / Joining",
    "Thermal Processing",
    "Surface Treatment",
    "Assembly",
    "Inspection",
    "Packaging & Dispatch",
    "Storage",
]

colA, colB = st.columns([2, 3], gap="large")

with colA:
    st.subheader("Process blocks")
    st.write("Add blocks in order (MVP: linear flow, no loops).")

    library = st.multiselect(
        "Pick from generic library",
        DEFAULT_LIBRARY,
        default=["Material Intake", "Cutting", "Forming", "Welding / Joining", "Surface Treatment", "Assembly", "Packaging & Dispatch"]
    )

    if "process_blocks" not in st.session_state:
        st.session_state.process_blocks = []

    add_block = st.selectbox("Add a block", ["—"] + library)
    if st.button("Add block", use_container_width=True) and add_block != "—":
        st.session_state.process_blocks.append({
            "name": add_block,
            "user_label": add_block,
            "type": suggest_process_type(add_block),
            "yield_pct": 92,
            "primary_material": "Mild steel sheet 2mm",
            "throughput_unit": "kg",
        })

    if st.session_state.process_blocks:
        st.write("Current flow:")
        for i, b in enumerate(st.session_state.process_blocks, start=1):
            st.write(f"{i}. **{b['user_label']}**  ·  *(type: {b['type']})*")

        if st.button("Remove last block", use_container_width=True):
            st.session_state.process_blocks = st.session_state.process_blocks[:-1]
    else:
        st.info("Add at least 3 blocks to make a meaningful map.")

with colB:
    st.subheader("Block details (lightweight)")
    st.write("Keep it minimal — just enough to do mass balance and explain assumptions.")

    if not st.session_state.process_blocks:
        st.stop()

    idx = st.number_input("Select block #", min_value=1, max_value=len(st.session_state.process_blocks), value=1, step=1)
    block = st.session_state.process_blocks[idx - 1]

    block["user_label"] = st.text_input("Block label", value=block["user_label"], key=f"label_{idx}")
    block["type"] = st.selectbox(
        "Process type",
        ["intake", "prep", "cutting", "forming", "joining", "thermal", "surface", "assembly", "inspection", "packaging", "storage", "other"],
        index=["intake","prep","cutting","forming","joining","thermal","surface","assembly","inspection","packaging","storage","other"].index(block["type"]),
        key=f"type_{idx}"
    )

    st.markdown("**Primary material & throughput unit**")
    block["primary_material"] = st.text_input("Primary input material (free text)", value=block.get("primary_material", ""), key=f"mat_{idx}")
    block["throughput_unit"] = st.selectbox("Throughput unit", ["kg", "pcs", "m2"], index=["kg","pcs","m2"].index(block.get("throughput_unit", "kg")), key=f"unit_{idx}")

    st.markdown("**Yield / losses (optional)**")
    block["yield_pct"] = st.slider("Estimated yield (%)", min_value=60, max_value=100, value=int(block.get("yield_pct", 92)), step=1, key=f"yield_{idx}")

# -----------------------------
# Step 2: Data inputs
# -----------------------------
st.header("2) Provide data (synthetic bundle or uploads)")
st.write("MVP supports: production output, material purchases, site energy, waste summary.")

bundle = None
if demo_mode:
    with st.expander("Synthetic data bundle (click to view)", expanded=True):
        bundle = make_synthetic_bundle()
        st.success("Synthetic data loaded.")

        tabs = st.tabs(["production_output", "material_purchases", "energy_site", "waste_summary"])
        tabs[0].dataframe(bundle["production_output"], use_container_width=True)
        tabs[1].dataframe(bundle["material_purchases"], use_container_width=True)
        tabs[2].dataframe(bundle["energy_site"], use_container_width=True)
        tabs[3].dataframe(bundle["waste_summary"], use_container_width=True)
else:
    st.info("Upload CSV/XLSX. AI will suggest what each file is and how to map columns (confirmable).")
    uploads = st.file_uploader("Upload one or more files", type=["csv", "xlsx"], accept_multiple_files=True)
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
            st.caption(f"AI suggestion: **{dtype}** (confirm below)")
            dtype_confirm = st.selectbox(
                f"Confirm type for {name}",
                ["production_output", "material_purchases", "energy_site", "waste_summary"],
                index=["production_output","material_purchases","energy_site","waste_summary"].index(dtype)
            )
            mapping = suggest_column_mapping(dtype_confirm, df)
            st.write("AI column mapping suggestion (edit if needed):")
            st.json(mapping)
            bundle[dtype_confirm] = df
            st.dataframe(df.head(20), use_container_width=True)

if bundle is None:
    st.stop()

# -----------------------------
# Step 3: Compute continuously (so scenarios update live)
# -----------------------------
st.header("3) Results (updates live with scenarios)")

model = build_flow_model(
    site_name=site_name,
    boundary_start=boundary_start,
    boundary_end=boundary_end,
    process_blocks=st.session_state.process_blocks,
    data_bundle=bundle,
    time_period=time_period,
    scenarios=scenarios,
)

results = compute_balances(model)
sankey = build_sankey_inputs(results)

top_left, top_right = st.columns([2, 1], gap="large")
with top_left:
    st.subheader("Material Flow Map (Sankey)")
    fig = render_sankey(sankey, title=f"{site_name} — {boundary_start} → {boundary_end}")
    st.plotly_chart(fig, use_container_width=True)

with top_right:
    st.subheader("KPIs")
    render_kpis(results)

    st.subheader("AI assist highlights")
    if results["ai_messages"]:
        for msg in results["ai_messages"]:
            st.write(f"• {msg}")
    else:
        st.write("• (No AI highlights yet — try scenarios or add more data.)")

    st.subheader("Assumptions & data gaps")
    for a in results["assumptions"]:
        st.write(f"• {a}")

st.divider()

tab1, tab2, tab3 = st.tabs(["Energy", "Circular economy", "Computed flows"])
with tab1:
    st.subheader("Energy usage & intensity")
    render_energy(results)

with tab2:
    st.subheader("Circular economy view")
    render_circularity(results)

with tab3:
    st.subheader("Computed flows (transparent)")
    st.dataframe(results["flows_table"], use_container_width=True)
