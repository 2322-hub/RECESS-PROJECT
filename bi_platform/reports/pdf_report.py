import io
import logging
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """Generate PDF reports from dashboard data."""

    @staticmethod
    def generate(dashboard_data: dict, title: str = "BI Dashboard Report") -> bytes:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), topMargin=0.5 * inch, bottomMargin=0.5 * inch)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(title, styles["Title"]))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]))
        elements.append(Spacer(1, 20))

        kpis = dashboard_data.get("kpis", {})
        if kpis:
            elements.append(Paragraph("Key Performance Indicators", styles["Heading2"]))
            kpi_data = [
                ["Metric", "Value"],
                ["Total Revenue", f"UGX {kpis.get('total_revenue', 0):,.2f}"],
                ["Total Profit", f"UGX {kpis.get('total_profit', 0):,.2f}"],
                ["Profit Margin", f"{kpis.get('profit_margin', 0):.1f}%"],
                ["Total Cost", f"UGX {kpis.get('total_cost', 0):,.2f}"],
                ["Records", f"{kpis.get('record_count', 0):,}"],
            ]
            t = Table(kpi_data, colWidths=[3 * inch, 3 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, 0), 11),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
                ("FONTSIZE", (0, 1), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))

        rb = dashboard_data.get("revenue_breakdown", {})
        if rb.get("region"):
            elements.append(Paragraph("Revenue by Region", styles["Heading2"]))
            region_data = [["Region", "Revenue (UGX)"]]
            for item in rb["region"]:
                region_data.append([item["label"], f"UGX {item['value']:,.2f}"])
            t = Table(region_data, colWidths=[3 * inch, 3 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#10b981")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))

        pp = dashboard_data.get("product_performance", [])
        if pp:
            elements.append(Paragraph("Product Performance", styles["Heading2"]))
            prod_data = [["Category", "Product", "Revenue", "Profit", "Quantity"]]
            for p in pp[:20]:
                prod_data.append([
                    p.get("product_category", ""),
                    p.get("product_name", ""),
                    f"UGX {p.get('total_revenue', 0):,.2f}",
                    f"UGX {p.get('profit', 0):,.2f}",
                    f"{p.get('quantity', 0):,}",
                ])
            t = Table(prod_data, colWidths=[1.5 * inch, 1.5 * inch, 2 * inch, 2 * inch, 1 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f59e0b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))

        wa = dashboard_data.get("website_analytics", {})
        if wa and wa.get("total_page_views"):
            elements.append(Paragraph("Website Analytics", styles["Heading2"]))
            wa_data = [
                ["Metric", "Value"],
                ["Page Views", f"{wa.get('total_page_views', 0):,}"],
                ["Unique Visitors", f"{wa.get('total_unique_visitors', 0):,}"],
                ["Bounce Rate", f"{wa.get('avg_bounce_rate', 0):.1f}%"],
                ["Conversions", f"{wa.get('total_conversions', 0):,}"],
                ["Conversion Rate", f"{wa.get('conversion_rate', 0):.1f}%"],
            ]
            t = Table(wa_data, colWidths=[3 * inch, 3 * inch])
            t.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#8b5cf6")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f0")]),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
            ]))
            elements.append(t)

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()
