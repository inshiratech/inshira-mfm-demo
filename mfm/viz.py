import streamlit as st
import plotly.graph_objects as go

def render_sankey(sankey, title="Material Flow Map"):
    fig = go.Figure(data=[go.Sankey(
        node=dict(label=sankey["labels"], pad=15, thickness=18),
        link=dict(source=sankey["sources"], target=sankey["targets"], value=sankey["values"])
    )])
    fig.update_layout(title_text=title, font_size=12)
    return fig

def render_kpis(results):
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Material in (kg)", f"{results['mat_in_kg']:,.0f}")
        st.metric("Product out (kg)", f"{results['prod_out_kg']:,.0f}")
        st.metric("Material efficiency (%)", f"{results['material_eff_pct']:.1f}")
    with c2:
        st.metric("Waste out (kg)", f"{results['waste_out_kg']:,.0f}")
        st.metric("Unaccounted loss (kg)", f"{results['unaccounted_kg']:,.0f}")
        st.metric("Waste intensity (kg waste / kg product)", f"{results['waste_intensity']:.3f}")

def render_energy(results):
    st.metric("Electricity (kWh)", f"{results['energy_elec_kwh']:,.0f}")
    st.metric("Gas (kWh)", f"{results['energy_gas_kwh']:,.0f}")
    st.metric("Energy intensity (kWh/kg product)", f"{results['energy_intensity_kwh_per_kg']:.3f}")

    if results.get("energy_alloc_table") is not None:
        st.caption("Allocated energy by process (proxy-based; editable assumption)")
        st.dataframe(results["energy_alloc_table"], use_container_width=True)

def render_circularity(results):
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Diverted from landfill (kg)", f"{results['diverted_kg']:,.0f}")
    with c2:
        st.metric("Diversion rate (%)", f"{results['diversion_pct']:.1f}")

    if results.get("waste_by_type") is not None and not results["waste_by_type"].empty:
        st.caption("Waste by type")
        st.dataframe(results["waste_by_type"], use_container_width=True)

    st.caption("Circular opportunities (rule-based prompts)")
    if results.get("opportunities"):
        for o in results["opportunities"]:
            st.write(f"• {o}")
    else:
        st.write("• Not enough detail to suggest opportunities yet.")
