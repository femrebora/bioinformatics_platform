"""
PDF report generator for the Mutation Assessment pipeline.
Uses reportlab (pure Python, no browser dependency).
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing, String

# ── Significance colours ───────────────────────────────────────────────────

_SIG_COLORS: dict[str, colors.Color] = {
    "pathogenic":           colors.HexColor("#dc2626"),
    "likely pathogenic":    colors.HexColor("#ea580c"),
    "uncertain significance": colors.HexColor("#ca8a04"),
    "likely benign":        colors.HexColor("#64748b"),
    "benign":               colors.HexColor("#16a34a"),
}

def _sig_color(sig: str) -> colors.Color:
    s = sig.lower()
    for key, col in _SIG_COLORS.items():
        if key in s:
            return col
    return colors.HexColor("#9ca3af")


def _sig_counts(variants: list[dict[str, Any]]) -> dict[str, int]:
    buckets = {
        "Pathogenic": 0,
        "Likely pathogenic": 0,
        "VUS": 0,
        "Likely benign": 0,
        "Benign": 0,
        "Unknown": 0,
    }
    for v in variants:
        sig = v.get("significance", "").lower()
        if "likely pathogenic" in sig:
            buckets["Likely pathogenic"] += 1
        elif "pathogenic" in sig:
            buckets["Pathogenic"] += 1
        elif "likely benign" in sig:
            buckets["Likely benign"] += 1
        elif "benign" in sig:
            buckets["Benign"] += 1
        elif "uncertain" in sig or "vus" in sig:
            buckets["VUS"] += 1
        else:
            buckets["Unknown"] += 1
    return buckets


def _make_bar_chart(counts: dict[str, int]) -> Drawing:
    labels = list(counts.keys())
    values = list(counts.values())

    d = Drawing(380, 140)

    chart = VerticalBarChart()
    chart.x = 40
    chart.y = 20
    chart.width = 320
    chart.height = 100
    chart.data = [values]
    chart.strokeColor = colors.HexColor("#e5e7eb")
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = max(values) + 1 if values else 5
    chart.valueAxis.valueStep = max(1, (max(values) + 1) // 5) if values else 1
    chart.valueAxis.labels.fontName = "Helvetica"
    chart.valueAxis.labels.fontSize = 7
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = "Helvetica"
    chart.categoryAxis.labels.fontSize = 7
    chart.categoryAxis.labels.angle = 15
    chart.categoryAxis.labels.dy = -6

    bar_colors = [
        colors.HexColor("#dc2626"),
        colors.HexColor("#ea580c"),
        colors.HexColor("#ca8a04"),
        colors.HexColor("#64748b"),
        colors.HexColor("#16a34a"),
        colors.HexColor("#9ca3af"),
    ]
    for i, col in enumerate(bar_colors):
        chart.bars[0, i].fillColor = col

    d.add(chart)
    return d


def generate_pdf(
    job_id: str,
    variants: list[dict[str, Any]],
    output_path: str,
) -> str:
    """Write the mutation assessment PDF to output_path and return output_path."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title2", parent=styles["Title"], fontSize=18, spaceAfter=4,
        textColor=colors.HexColor("#111827"),
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontSize=11, spaceBefore=12, spaceAfter=4,
        textColor=colors.HexColor("#374151"),
    )
    normal = ParagraphStyle(
        "Normal2", parent=styles["Normal"], fontSize=9,
        textColor=colors.HexColor("#374151"),
    )
    disclaimer_style = ParagraphStyle(
        "Disclaimer", parent=styles["Normal"], fontSize=8,
        textColor=colors.HexColor("#9ca3af"), spaceAfter=0,
    )

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    story = []

    # ── Header ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Mutation Assessment Report", title_style))
    story.append(Paragraph(
        f"Job ID: <font name='Courier' size='8'>{job_id}</font> &nbsp;·&nbsp; "
        f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
        normal,
    ))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e5e7eb"), spaceAfter=8))

    # ── Summary stats ──────────────────────────────────────────────────────
    counts = _sig_counts(variants)
    total       = len(variants)
    pathogenic  = counts["Pathogenic"] + counts["Likely pathogenic"]
    hotspots    = sum(1 for v in variants if v.get("hotspot"))

    summary_data = [
        ["Total Variants", "Pathogenic / LP", "Cancer Hotspots"],
        [str(total), str(pathogenic), str(hotspots)],
    ]
    summary_table = Table(summary_data, colWidths=[5.5 * cm, 5.5 * cm, 5.5 * cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0), colors.HexColor("#f3f4f6")),
        ("FONTNAME",    (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, 0), 9),
        ("FONTNAME",    (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE",    (0, 1), (-1, 1), 18),
        ("TEXTCOLOR",   (0, 1), (0, 1), colors.HexColor("#111827")),
        ("TEXTCOLOR",   (1, 1), (1, 1), colors.HexColor("#dc2626")),
        ("TEXTCOLOR",   (2, 1), (2, 1), colors.HexColor("#d97706")),
        ("ALIGN",       (0, 0), (-1, -1), "CENTER"),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f9fafb"), colors.white]),
        ("BOX",         (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e7eb")),
        ("INNERGRID",   (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 8))

    # ── Classification bar chart ───────────────────────────────────────────
    if total > 0:
        story.append(Paragraph("Variant Classification", h2_style))
        story.append(_make_bar_chart(counts))
        story.append(Spacer(1, 8))

    # ── Variant annotation table ───────────────────────────────────────────
    story.append(Paragraph("Annotated Variants", h2_style))

    headers = ["Chr", "Pos", "Ref", "Alt", "Gene", "Classification", "Hotspot", "AF", "rsID"]
    table_data = [headers]

    for v in variants:
        af_raw = v.get("af")
        af_str = f"{af_raw:.4f}" if isinstance(af_raw, (int, float)) else "—"
        table_data.append([
            str(v.get("chrom", "")),
            str(v.get("pos", "")),
            str(v.get("ref", "")),
            str(v.get("alt", "")),
            str(v.get("gene", "—")),
            str(v.get("significance", "Unknown")),
            "✓" if v.get("hotspot") else "—",
            af_str,
            str(v.get("rsid", ".")),
        ])

    col_widths = [1.5*cm, 2.0*cm, 1.2*cm, 1.2*cm, 1.8*cm, 4.2*cm, 1.4*cm, 1.5*cm, 2.5*cm]
    var_table = Table(table_data, colWidths=col_widths, repeatRows=1)

    ts = [
        ("BACKGROUND",    (0, 0), (-1, 0), colors.HexColor("#1e3a5f")),
        ("TEXTCOLOR",     (0, 0), (-1, 0), colors.white),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 7),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID",          (0, 0), (-1, -1), 0.3, colors.HexColor("#e5e7eb")),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("ALIGN",         (4, 1), (5, -1), "LEFT"),   # Gene + Significance left-aligned
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    # Highlight pathogenic rows in light red
    for row_i, v in enumerate(variants, start=1):
        sig = v.get("significance", "").lower()
        if "pathogenic" in sig:
            bg = colors.HexColor("#fff1f2") if "likely" in sig else colors.HexColor("#fee2e2")
            ts.append(("BACKGROUND", (0, row_i), (-1, row_i), bg))
        # Color the significance cell
        ts.append(("TEXTCOLOR", (5, row_i), (5, row_i), _sig_color(v.get("significance", ""))))
        ts.append(("FONTNAME",  (5, row_i), (5, row_i), "Helvetica-Bold"))

    var_table.setStyle(TableStyle(ts))
    story.append(var_table)
    story.append(Spacer(1, 12))

    # ── Databases queried ──────────────────────────────────────────────────
    story.append(Paragraph("Data Sources", h2_style))
    story.append(Paragraph(
        "<b>Franklin by Genoox</b> (franklin.genoox.com) — primary ACMG variant classification, "
        "gene annotation, gnomAD population allele frequencies, and disease associations. "
        "<b>ClinVar (NCBI)</b> — clinical significance and pathogenicity classifications (fallback/supplement). "
        "<b>CancerHotspots.org</b> — recurrent cancer driver mutation hotspots. "
        "<b>dbSNP (NCBI)</b> — population variant rsID identifiers.",
        normal,
    ))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e5e7eb"), spaceAfter=6))

    # ── Disclaimer ─────────────────────────────────────────────────────────
    story.append(Paragraph(
        "⚠ RESEARCH USE ONLY — This report is generated automatically from public databases "
        "and is NOT intended for clinical diagnosis, treatment, or patient care decisions. "
        "Variant interpretations may be incomplete or inaccurate. Always consult a certified "
        "clinical geneticist or medical professional for clinical variant interpretation.",
        disclaimer_style,
    ))

    doc.build(story)
    return output_path
