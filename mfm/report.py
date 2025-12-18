from io import BytesIO
from datetime import datetime
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def _safe_text(s: str) -> str:
    return (s or "").replace("\n", " ").strip()

def build_pdf_report(site_name: str, boundary_start: str, boundary_end: str, results: dict, sankey_fig=None) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    y = h - 50
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Gate-to-Gate Material Flow Map Report")
    y -= 22
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Site: {_safe_text(site_name)}")
    y -= 16
    c.drawString(40, y, f"Boundary: {_safe_text(boundary_start)}  →  {_safe_text(boundary_end)}")
    y -= 16
    c.drawString(40, y, f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    y -= 22

    # KPIs
    c.setFont("Helvetica-Bold", 12)
    c.drawString(40, y, "Key KPIs")
    y -= 16
    c.setFont("Helvetica", 11)

    kpis = [
        ("Material in (kg)", f"{results['mat_in_kg']:,.0f}"),
        ("Product out (kg)", f"{results['prod_out_kg']:,.0f}"),
        ("Waste out (kg)", f"{results['waste_out_kg']:,.0f}"),
        ("Unaccounted loss (kg)", f"{results['unaccounted_kg']:,.0f}"),
        ("Material efficiency (%)", f"{results['material_eff_pct']:.1f}"),
        ("Energy (kWh) electricity", f"{results['energy_elec_kwh']:,.0f}"),
        ("Energy (kWh) gas", f"{results['energy_gas_kwh']:,.0f}"),
        ("Energy intensity (kWh/kg product)", f"{results['energy_intensity_kwh_per_kg']:.3f}"),
        ("Diversion rate (%)", f"{results['diversion_pct']:.1f}"),
    ]
    for k, v in kpis:
        c.drawString(50, y, f"{k}: {v}")
        y -= 14
        if y < 120:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 11)

    # Sankey image (optional)
    if sankey_fig is not None:
        try:
            img_bytes = sankey_fig.to_image(format="png", width=1200, height=650, scale=2)
            img = ImageReader(BytesIO(img_bytes))
            c.setFont("Helvetica-Bold", 12)
            c.drawString(40, y, "Material Flow Map")
            y -= 10
            # Fit image nicely
            img_w = w - 80
            img_h = img_w * 0.54
            if y - img_h < 60:
                c.showPage()
                y = h - 50
            c.drawImage(img, 40, y - img_h, width=img_w, height=img_h, preserveAspectRatio=True, mask='auto')
            y -= (img_h + 18)
        except Exception:
            # Keep report usable even if kaleido/image export fails
            c.setFont("Helvetica", 10)
            c.drawString(40, y, "Note: Sankey image export unavailable in this environment.")
            y -= 16

    # AI + assumptions
    def bullet_section(title: str, items: list[str]):
        nonlocal y
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, title)
        y -= 16
        c.setFont("Helvetica", 11)
        if not items:
            c.drawString(50, y, "• (none)")
            y -= 14
            return
        for it in items:
            text = _safe_text(it)
            c.drawString(50, y, f"• {text[:120]}")
            y -= 14
            if y < 60:
                c.showPage()
                y = h - 50
                c.setFont("Helvetica", 11)

    bullet_section("AI assist highlights", results.get("ai_messages", []))
    bullet_section("Assumptions & data gaps", results.get("assumptions", []))
    bullet_section("Circular opportunities", results.get("opportunities", []))

    # Small tables (top rows only)
    def add_table(title: str, df: pd.DataFrame, max_rows=12):
        nonlocal y
        if df is None or df.empty:
            return
        c.setFont("Helvetica-Bold", 12)
        c.drawString(40, y, title)
        y -= 14
        c.setFont("Helvetica", 9)

        dfx = df.head(max_rows).copy()
        cols = list(dfx.columns)
        x0 = 40
        col_w = (w - 80) / max(len(cols), 1)

        # header
        for i, col in enumerate(cols):
            c.drawString(x0 + i * col_w, y, str(col)[:18])
        y -= 12

        # rows
        for _, row in dfx.iterrows():
            for i, col in enumerate(cols):
                c.drawString(x0 + i * col_w, y, str(row[col])[:18])
            y -= 11
            if y < 60:
                c.showPage()
                y = h - 50
                c.setFont("Helvetica", 9)

        y -= 10

    add_table("Computed flows (sample)", results.get("flows_table"))
    add_table("Waste by type (sample)", results.get("waste_by_type"))
    if results.get("energy_alloc_table") is not None:
        add_table("Energy allocation by process (sample)", results.get("energy_alloc_table"))

    c.save()
    return buf.getvalue()
