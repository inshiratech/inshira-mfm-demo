import pandas as pd
import numpy as np

def build_flow_model(site_name, boundary_start, boundary_end, process_blocks, data_bundle, time_period, scenarios):
    return {
        "site_name": site_name,
        "boundary_start": boundary_start,
        "boundary_end": boundary_end,
        "blocks": process_blocks,
        "data": data_bundle,
        "time_period": time_period,
        "scenarios": scenarios,
    }

def _find_col(df, keywords):
    for c in df.columns:
        lc = c.lower()
        if any(k in lc for k in keywords):
            return c
    return None

def _sum_material_in_kg(material_df):
    kg_col = _find_col(material_df, ["kg", "weight"])
    return float(material_df[kg_col].astype(float).sum()) if kg_col else None

def _sum_waste_kg(waste_df):
    kg_col = _find_col(waste_df, ["kg", "quantity"])
    return float(waste_df[kg_col].astype(float).sum()) if kg_col else None

def _sum_waste_by_type(waste_df):
    type_col = _find_col(waste_df, ["waste"])
    kg_col = _find_col(waste_df, ["kg", "quantity"])
    if not type_col or not kg_col:
        return pd.DataFrame(columns=["Waste Type", "Quantity (kg)"])
    out = (waste_df[[type_col, kg_col]]
           .rename(columns={type_col: "Waste Type", kg_col: "Quantity (kg)"})
           .copy())
    out["Quantity (kg)"] = out["Quantity (kg)"].astype(float)
    return out

def _energy_totals(energy_df):
    elec_col = _find_col(energy_df, ["electric"])
    gas_col  = _find_col(energy_df, ["gas"])
    elec = float(energy_df[elec_col].sum()) if elec_col else 0.0
    gas  = float(energy_df[gas_col].sum())  if gas_col else 0.0
    return elec, gas, bool(elec_col or gas_col)

def compute_balances(model):
    data = model["data"]
    blocks = model["blocks"]
    sc = model["scenarios"]

    ai_messages = []
    assumptions = []

    # ---------- Inputs ----------
    mat_in = _sum_material_in_kg(data["material_purchases"])
    if mat_in is None:
        mat_in = 0.0
        assumptions.append("Material input mass missing; treated as 0 kg.")

    waste_df = data["waste_summary"]
    waste_out = _sum_waste_kg(waste_df)
    if waste_out is None:
        waste_out = 0.0
        assumptions.append("Waste mass missing; treated as 0 kg.")

    # Production (pcs → kg via demo assumption)
    prod_df = data["production_output"]
    qty_col = _find_col(prod_df, ["qty", "produced", "quantity"])
    qty = float(prod_df[qty_col].sum()) if qty_col else 0.0
    assumed_unit_mass = 15.0  # demo default
    prod_mass_out_base = qty * assumed_unit_mass
    assumptions.append(f"Converted output to mass using assumed unit mass = {assumed_unit_mass:.1f} kg/pc (demo assumption).")

    # ---------- Scenarios ----------
    # 1) Scrap reduction reduces waste_out (recycling/landfill streams) proportionally
    scrap_reduction_pct = sc.get("scrap_reduction_pct", 0.0) / 100.0
    waste_out_scn = waste_out * (1.0 - scrap_reduction_pct)
    if scrap_reduction_pct > 0:
        ai_messages.append(f"Scenario applied: scrap/waste reduced by {sc.get('scrap_reduction_pct', 0.0):.0f}%.")

    # 2) Yield improvement increases product output mass (simple proxy)
    yield_improve_pct = sc.get("yield_improve_pct", 0.0) / 100.0
    prod_mass_out = prod_mass_out_base * (1.0 + yield_improve_pct)
    if yield_improve_pct > 0:
        ai_messages.append(f"Scenario applied: yield improved by {sc.get('yield_improve_pct', 0.0):.0f}% (proxy increases product output).")

    # 3) Energy intensity improvement reduces total energy
    energy_intensity_improve_pct = sc.get("energy_intensity_improve_pct", 0.0) / 100.0

    # ---------- Unaccounted material ----------
    unaccounted = max(mat_in - prod_mass_out - waste_out_scn, 0.0)

    # Attribute unaccounted to cutting/forming where possible
    loss_targets = [b for b in blocks if b.get("type") in ("cutting", "forming")]
    if not loss_targets:
        loss_targets = [blocks[0]]

    if len(loss_targets) >= 2:
        split = np.array([0.6, 0.4])
        split = split[:len(loss_targets)]
        split = split / split.sum()
    else:
        split = np.array([1.0])

    losses = {loss_targets[i]["user_label"]: unaccounted * float(split[i]) for i in range(len(loss_targets))}

    if unaccounted > 0:
        ai_messages.append(f"Detected ~{unaccounted:,.0f} kg unaccounted material. Likely process losses (offcuts/rejects). Flagged for review.")
        assumptions.append("Unaccounted material attributed to cutting/forming losses (demo heuristic).")

    # ---------- Energy ----------
    energy_df = data["energy_site"]
    elec_kwh, gas_kwh, has_energy = _energy_totals(energy_df)
    if has_energy:
        if energy_intensity_improve_pct > 0:
            elec_kwh *= (1.0 - energy_intensity_improve_pct)
            gas_kwh  *= (1.0 - energy_intensity_improve_pct)
            ai_messages.append(f"Scenario applied: energy intensity improved by {sc.get('energy_intensity_improve_pct', 0.0):.0f}% (reduces site kWh).")
        assumptions.append("Energy is site-level; allocation to processes is optional and uses a proxy (throughput shares).")

    # Optional: allocate energy across processes using throughput proxy weights
    allocate_energy = sc.get("allocate_energy", False)
    energy_alloc = None
    if has_energy and allocate_energy:
        # proxy weights: use yields as a stand-in for relative activity; fallback equal weights
        weights = []
        for b in blocks:
            y = float(b.get("yield_pct", 92))
            weights.append(max(y, 1.0))
        weights = np.array(weights, dtype=float)
        weights = weights / weights.sum() if weights.sum() > 0 else np.ones(len(blocks)) / len(blocks)

        energy_alloc = pd.DataFrame({
            "Process": [b["user_label"] for b in blocks],
            "Electricity_kWh": (elec_kwh * weights).round(0).astype(int),
            "Gas_kWh": (gas_kwh * weights).round(0).astype(int),
        })
        ai_messages.append("AI assist: allocated site energy to processes using a simple activity proxy (editable assumption).")

    # ---------- Circularity metrics ----------
    waste_by_type = _sum_waste_by_type(waste_df)
    # Diversion: count Recycling + Reuse as diverted (based on Disposal Route column if present)
    route_col = _find_col(waste_df, ["route", "disposal"])
    diverted_kg = 0.0
    if route_col:
        kg_col = _find_col(waste_df, ["kg", "quantity"])
        tmp = waste_df.copy()
        tmp[kg_col] = tmp[kg_col].astype(float)
        diverted_kg = float(tmp[tmp[route_col].astype(str).str.lower().isin(["recycling", "reuse"])][kg_col].sum())
    else:
        assumptions.append("No disposal route column detected; diversion % may be incomplete.")

    # Apply scrap reduction scenario to diversion and waste totals proportionally
    diverted_kg_scn = diverted_kg * (1.0 - scrap_reduction_pct)
    diversion_pct = (diverted_kg_scn / waste_out_scn * 100.0) if waste_out_scn > 0 else 0.0

    # Simple circular opportunities (rule-based, not hype)
    opportunities = []
    if not waste_by_type.empty:
        # steel scrap heuristic
        steel_row = waste_by_type[waste_by_type["Waste Type"].astype(str).str.lower().str.contains("steel|metal|scrap", regex=True)]
        if not steel_row.empty and float(steel_row["Quantity (kg)"].sum()) > 500:
            opportunities.append("High clean metal scrap: consider closed-loop recycling with supplier or local reprocessor.")
        mixed_row = waste_by_type[waste_by_type["Waste Type"].astype(str).str.lower().str.contains("mixed", regex=True)]
        if not mixed_row.empty and float(mixed_row["Quantity (kg)"].sum()) > 300:
            opportunities.append("Mixed waste is significant: segregation could increase recycling rate and reduce disposal cost.")
        sludge_row = waste_by_type[waste_by_type["Waste Type"].astype(str).str.lower().str.contains("sludge|hazard", regex=True)]
        if not sludge_row.empty and float(sludge_row["Quantity (kg)"].sum()) > 100:
            opportunities.append("Hazardous/sludge stream: review upstream process controls and chemical use to reduce generation.")

    # ---------- Build flows for Sankey ----------
    rows = []
    start = model["boundary_start"]
    end = model["boundary_end"]

    # Main input
    rows.append({"from": start, "to": blocks[0]["user_label"], "kg": mat_in, "kind": "material_in"})

    # Proxy throughput along the chain: show remaining “useful” mass
    useful_through = max(mat_in - waste_out_scn - unaccounted, 0.0)
    for i in range(len(blocks) - 1):
        rows.append({"from": blocks[i]["user_label"], "to": blocks[i+1]["user_label"], "kg": useful_through, "kind": "throughput_proxy"})

    # Outputs
    rows.append({"from": blocks[-1]["user_label"], "to": end, "kg": prod_mass_out, "kind": "product_out"})
    rows.append({"from": "All processes", "to": "Waste streams", "kg": waste_out_scn, "kind": "waste_out"})

    for k, v in losses.items():
        rows.append({"from": k, "to": "Process losses (unaccounted)", "kg": v, "kind": "loss_inferred"})

    flows_table = pd.DataFrame(rows)

    # ---------- KPIs ----------
    material_eff = (prod_mass_out / mat_in) * 100.0 if mat_in > 0 else 0.0
    waste_intensity = (waste_out_scn / prod_mass_out) if prod_mass_out > 0 else 0.0
    energy_intensity = ((elec_kwh + gas_kwh) / prod_mass_out) if prod_mass_out > 0 else 0.0

    return {
        "mat_in_kg": mat_in,
        "prod_out_kg": prod_mass_out,
        "waste_out_kg": waste_out_scn,
        "unaccounted_kg": unaccounted,
        "material_eff_pct": material_eff,
        "waste_intensity": waste_intensity,
        "energy_elec_kwh": elec_kwh,
        "energy_gas_kwh": gas_kwh,
        "energy_intensity_kwh_per_kg": energy_intensity,
        "energy_alloc_table": energy_alloc,
        "waste_by_type": waste_by_type,
        "diversion_pct": diversion_pct,
        "diverted_kg": diverted_kg_scn,
        "opportunities": opportunities,
        "ai_messages": ai_messages,
        "assumptions": assumptions,
        "flows_table": flows_table,
        "blocks": blocks,
        "boundary_start": start,
        "boundary_end": end,
    }

def build_sankey_inputs(results):
    flows = results["flows_table"].copy()
    labels = pd.unique(pd.concat([flows["from"], flows["to"]], ignore_index=True)).tolist()
    idx = {lab: i for i, lab in enumerate(labels)}
    sources = [idx[x] for x in flows["from"]]
    targets = [idx[x] for x in flows["to"]]
    values = flows["kg"].astype(float).tolist()
    return {"labels": labels, "sources": sources, "targets": targets, "values": values}
