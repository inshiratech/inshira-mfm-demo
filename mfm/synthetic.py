import pandas as pd

def make_synthetic_bundle():
    production_output = pd.DataFrame({
        "Date": ["2025-01-03","2025-01-10","2025-01-17","2025-01-24","2025-02-07","2025-02-14","2025-02-21","2025-03-07","2025-03-14","2025-03-21"],
        "Product Code": ["ENC-A"]*10,
        "Qty Produced": [480,510,495,470,520,505,490,515,500,510],
        "Unit": ["pcs"]*10
    })

    material_purchases = pd.DataFrame({
        "Month": ["Jan","Feb","Mar"],
        "Material Description": ["Mild steel sheet 2mm"]*3,
        "Weight (kg)": [12000,11500,12300]
    })

    energy_site = pd.DataFrame({
        "Month": ["Jan","Feb","Mar"],
        "Electricity_kWh": [38000,36500,39200],
        "Gas_kWh": [21000,19800,22100]
    })

    waste_summary = pd.DataFrame({
        "Waste Type": ["Steel scrap","Mixed waste","Sludge"],
        "Quantity (kg)": [3200,850,420],
        "Disposal Route": ["Recycling","Landfill","Hazardous"]
    })

    return {
        "production_output": production_output,
        "material_purchases": material_purchases,
        "energy_site": energy_site,
        "waste_summary": waste_summary,
    }
