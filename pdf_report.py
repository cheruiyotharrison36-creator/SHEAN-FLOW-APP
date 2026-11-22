
from __future__ import annotations

from io import BytesIO
from datetime import datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    Image,
    PageBreak,
    KeepTogether,
)


# --------------------------------------------------
# COLOURS AND REPORT STYLING
# --------------------------------------------------

NAVY = colors.HexColor("#17365D")
BLUE = colors.HexColor("#2874A6")
LIGHT_BLUE = colors.HexColor("#E8EFF7")
LIGHT_GREY = colors.HexColor("#F3F6FA")
GREY = colors.HexColor("#777777")


def make_table(data, col_widths, header=True):

    table = Table(
        data,
        colWidths=col_widths,
        repeatRows=1 if header else 0
    )

    commands = [
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]

    if header:
        commands.extend([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1),
             [colors.white, LIGHT_GREY]),
        ])

    table.setStyle(TableStyle(commands))

    return table


def create_pdf_report(
    project_name,
    prepared_by,
    channel,
    depth,
    geometry,
    diagram_figure=None,
    manning_results=None,
    critical_results=None,
    engineering_notes=""
):

    """
    Generate a professional SHEAN FLOW APP engineering report.

    Returns:
        PDF document as bytes.
    """

    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=22 * mm,
        title="SHEAN FLOW APP Engineering Report",
        author="SHEAN FLOW APP",
    )

    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="BrandTitle",
            parent=styles["Title"],
            fontSize=27,
            leading=33,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceAfter=12,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontSize=17,
            leading=22,
            alignment=TA_CENTER,
            textColor=NAVY,
            spaceAfter=10,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["Normal"],
            alignment=TA_CENTER,
            fontSize=9,
            leading=14,
            textColor=GREY,
            spaceAfter=12,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontSize=12,
            leading=16,
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=7,
            keepWithNext=True,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SmallText",
            parent=styles["Normal"],
            fontSize=8,
            leading=12,
            textColor=GREY,
        )
    )

    story = []

    # ==================================================
    # COVER PAGE
    # ==================================================

    story.append(Spacer(1, 28 * mm))

    story.append(
        Paragraph(
            "SHEAN FLOW APP",
            styles["BrandTitle"]
        )
    )

    story.append(
        Paragraph(
            "OPEN-CHANNEL HYDRAULIC ENGINEERING",
            styles["ReportTitle"]
        )
    )

    story.append(
        Paragraph(
            "TECHNICAL CALCULATION REPORT",
            styles["ReportSubtitle"]
        )
    )

    story.append(Spacer(1, 20 * mm))

    cover_data = [
        ["PROJECT INFORMATION", ""],
        ["Project name", escape(str(project_name or "Not specified"))],
        ["Prepared by", escape(str(prepared_by or "Not specified"))],
        ["Channel type", escape(str(channel.name))],
        ["Flow depth", f"{float(depth):.4f} m"],
        ["Report date", datetime.now().strftime("%d %B %Y")],
    ]

    cover_table = Table(
        cover_data,
        colWidths=[48 * mm, 112 * mm]
    )

    cover_table.setStyle(
        TableStyle([
            ("SPAN", (0, 0), (-1, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), NAVY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("BACKGROUND", (0, 1), (0, -1), LIGHT_BLUE),
            ("TEXTCOLOR", (0, 1), (0, -1), NAVY),
            ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ])
    )

    story.append(cover_table)

    story.append(Spacer(1, 25 * mm))

    story.append(
        Paragraph(
            "Prepared using SHEAN FLOW APP",
            ParagraphStyle(
                name="CoverFooter",
                parent=styles["Normal"],
                alignment=TA_CENTER,
                fontSize=10,
                textColor=BLUE,
            )
        )
    )

    story.append(PageBreak())

    # ==================================================
    # 1. PROJECT INFORMATION
    # ==================================================

    story.append(
        Paragraph(
            "1. PROJECT INFORMATION",
            styles["SectionHeading"]
        )
    )

    project_data = [
        ["Description", "Details"],
        ["Project", escape(str(project_name or "Not specified"))],
        ["Prepared by", escape(str(prepared_by or "Not specified"))],
        ["Report date", datetime.now().strftime("%d %B %Y")],
        ["Channel type", escape(str(channel.name))],
        ["Flow depth", f"{float(depth):.4f} m"],
    ]

    story.append(
        make_table(
            project_data,
            [55 * mm, 115 * mm]
        )
    )

    # ==================================================
    # 2. CHANNEL DIMENSIONS
    # ==================================================

    story.append(
        Paragraph(
            "2. CHANNEL DIMENSIONS",
            styles["SectionHeading"]
        )
    )

    dimensions = [
        ["Parameter", "Value", "Unit"]
    ]

    if hasattr(channel, "b"):
        dimensions.append(
            ["Bottom width, b", f"{channel.b:.4f}", "m"]
        )

    if hasattr(channel, "m"):
        dimensions.append(
            ["Left side slope, m", f"{channel.m:.4f}", "H:V"]
        )

    if hasattr(channel, "n"):
        dimensions.append(
            ["Right side slope, n", f"{channel.n:.4f}", "H:V"]
        )

    if hasattr(channel, "D"):
        dimensions.append(
            ["Pipe diameter, D", f"{channel.D:.4f}", "m"]
        )

    dimensions.append(
        ["Flow depth, y", f"{float(depth):.4f}", "m"]
    )

    story.append(
        make_table(
            dimensions,
            [75 * mm, 50 * mm, 45 * mm]
        )
    )

    # ==================================================
    # 3. CHANNEL CROSS-SECTION
    # ==================================================

    if diagram_figure is not None:

        story.append(
            Paragraph(
                "3. CHANNEL CROSS-SECTION DIAGRAM",
                styles["SectionHeading"]
            )
        )

        image_buffer = BytesIO()

        diagram_figure.savefig(
            image_buffer,
            format="png",
            dpi=200,
            bbox_inches="tight"
        )

        image_buffer.seek(0)

        diagram_image = Image(
            image_buffer,
            width=145 * mm,
            height=95 * mm,
            kind="proportional"
        )

        story.append(
            KeepTogether([
                diagram_image,
                Paragraph(
                    "Figure 1: Selected channel cross-section.",
                    styles["SmallText"]
                )
            ])
        )

    # ==================================================
    # 4. GEOMETRIC AND HYDRAULIC PROPERTIES
    # ==================================================

    story.append(
        Paragraph(
            "4. GEOMETRIC AND HYDRAULIC PROPERTIES",
            styles["SectionHeading"]
        )
    )

    property_labels = {
        "A": ("Flow area, A", "m²"),
        "P": ("Wetted perimeter, P", "m"),
        "B": ("Top width, B", "m"),
        "R": ("Hydraulic radius, R", "m"),
        "D_h": ("Hydraulic depth, Dh", "m"),
    }

    property_data = [
        ["Property", "Calculated value", "Unit"]
    ]

    for key, (label, unit) in property_labels.items():

        if key in geometry:

            value = geometry[key]

            if value is not None:
                try:
                    value_text = f"{float(value):.4f}"
                except (TypeError, ValueError):
                    value_text = str(value)
            else:
                value_text = "Not available"

            property_data.append(
                [label, value_text, unit]
            )

    story.append(
        make_table(
            property_data,
            [75 * mm, 50 * mm, 45 * mm]
        )
    )

    # ==================================================
    # 5. MANNING FLOW ANALYSIS
    # ==================================================

    if manning_results:

        story.append(
            Paragraph(
                "5. MANNING UNIFORM FLOW ANALYSIS",
                styles["SectionHeading"]
            )
        )

        story.append(
            Paragraph(
                "Manning's equation for uniform open-channel flow:",
                styles["Normal"]
            )
        )

        story.append(Spacer(1, 3 * mm))

        story.append(
            Paragraph(
                "Q = (1/n) A R^(2/3) S0^(1/2)",
                styles["Normal"]
            )
        )

        story.append(Spacer(1, 3 * mm))

        manning_data = [
            ["Parameter", "Calculated value"]
        ]

        for label, value in manning_results.items():

            manning_data.append([
                escape(str(label)),
                escape(str(value))
            ])

        story.append(
            make_table(
                manning_data,
                [85 * mm, 85 * mm]
            )
        )

    else:

        story.append(
            Paragraph(
                "5. MANNING UNIFORM FLOW ANALYSIS",
                styles["SectionHeading"]
            )
        )

        story.append(
            Paragraph(
                "No Manning calculation results were supplied "
                "for this report.",
                styles["SmallText"]
            )
        )

    # ==================================================
    # 6. CRITICAL FLOW ANALYSIS
    # ==================================================

    if critical_results:

        story.append(
            Paragraph(
                "6. CRITICAL FLOW ANALYSIS",
                styles["SectionHeading"]
            )
        )

        story.append(
            Paragraph(
                "Critical flow occurs when the Froude number is "
                "equal to unity. The critical-flow condition is:",
                styles["Normal"]
            )
        )

        story.append(Spacer(1, 3 * mm))

        story.append(
            Paragraph(
                "Q² B / (g A³) = 1",
                styles["Normal"]
            )
        )

        story.append(Spacer(1, 3 * mm))

        critical_data = [
            ["Parameter", "Calculated value"]
        ]

        for label, value in critical_results.items():

            critical_data.append([
                escape(str(label)),
                escape(str(value))
            ])

        story.append(
            make_table(
                critical_data,
                [85 * mm, 85 * mm]
            )
        )

    else:

        story.append(
            Paragraph(
                "6. CRITICAL FLOW ANALYSIS",
                styles["SectionHeading"]
            )
        )

        story.append(
            Paragraph(
                "No critical-flow calculation results were supplied "
                "for this report.",
                styles["SmallText"]
            )
        )

    # ==================================================
    # 7. ENGINEERING NOTES
    # ==================================================

    story.append(
        Paragraph(
            "7. ENGINEERING NOTES AND OBSERVATIONS",
            styles["SectionHeading"]
        )
    )

    notes = escape(
        engineering_notes or
        "No additional engineering observations were provided."
    ).replace("\n", "<br/>")

    story.append(
        Paragraph(
            notes,
            styles["BodyText"]
        )
    )

    # ==================================================
    # 8. ENGINEERING VERIFICATION
    # ==================================================

    story.append(
        Paragraph(
            "8. ENGINEERING VERIFICATION NOTICE",
            styles["SectionHeading"]
        )
    )

    story.append(
        Paragraph(
            "This report is generated by SHEAN FLOW APP as an "
            "engineering calculation aid. The accuracy of the "
            "results depends on the supplied input data, "
            "assumptions and calculation methods. An appropriately "
            "qualified engineer should independently verify the "
            "results, design criteria, material suitability and "
            "applicable engineering standards before construction "
            "or implementation.",
            styles["BodyText"]
        )
    )

    # ==================================================
    # PAGE FOOTER
    # ==================================================

    def add_footer(canvas, doc):

        canvas.saveState()

        canvas.setStrokeColor(
            colors.HexColor("#B7C9DA")
        )

        canvas.line(
            18 * mm,
            14 * mm,
            192 * mm,
            14 * mm
        )

        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(GREY)

        canvas.drawString(
            18 * mm,
            9 * mm,
            "SHEAN FLOW APP | Hydraulic Engineering Report"
        )

        canvas.drawRightString(
            192 * mm,
            9 * mm,
            f"Page {doc.page}"
        )

        canvas.restoreState()

    # ==================================================
    # BUILD PDF
    # ==================================================

    document.build(
        story,
        onFirstPage=add_footer,
        onLaterPages=add_footer
    )

    pdf_bytes = buffer.getvalue()

    buffer.close()

    return pdf_bytes
