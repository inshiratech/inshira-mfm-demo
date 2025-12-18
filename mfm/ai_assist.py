import re

def suggest_dataset_type(filename, df):
    name = filename.lower()
    cols = " ".join([c.lower() for c in df.columns])

    if "kwh" in cols or "electric" in cols or "gas" in cols or "energy" in name:
        return "energy_site"
    if "waste" in name or "disposal" in cols or "waste type" in cols:
        return "waste_summary"
    if "purchase" in name or "material" in cols and ("kg" in cols or "weight" in cols):
        return "material_purchases"
    return "production_output"

def suggest_column_mapping(dataset_type, df):
    cols = [c for c in df.columns]
    low = {c.lower(): c for c in cols}

    def pick(*keys):
        for k in keys:
            for lc, orig in low.items():
                if k in lc:
                    return orig
        return None

    if dataset_type == "production_output":
        return {"date": pick("date"), "qty": pick("qty", "quantity", "produced"), "unit": pick("unit"), "product": pick("product")}
    if dataset_type == "material_purchases":
        return {"period": pick("month", "period"), "material": pick("material"), "mass_kg": pick("kg", "weight")}
    if dataset_type == "energy_site":
        return {"period": pick("month", "period"), "electricity_kwh": pick("electric", "kwh"), "gas_kwh": pick("gas")}
    if dataset_type == "waste_summary":
        return {"waste_type": pick("waste"), "mass_kg": pick("kg", "quantity"), "route": pick("route", "disposal")}
    return {}

def suggest_process_type(label):
    s = label.lower()
    if "intake" in s or "goods in" in s:
        return "intake"
    if "cut" in s or "laser" in s:
        return "cutting"
    if "form" in s or "press" in s or "brake" in s:
        return "forming"
    if "weld" in s or "join" in s:
        return "joining"
    if "coat" in s or "paint" in s or "treat" in s:
        return "surface"
    if "assembl" in s:
        return "assembly"
    if "pack" in s or "dispatch" in s:
        return "packaging"
    if "inspect" in s:
        return "inspection"
    return "other"
