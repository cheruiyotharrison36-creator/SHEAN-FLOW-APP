"""Single-page, calculation-specific PDF summaries."""
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

def make_compact_report(calculation):
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=45, rightMargin=45, topMargin=45, bottomMargin=45)
    styles = getSampleStyleSheet()
    title = escape(str(calculation['title']))
    story = [Paragraph('SHEAN FLOW | HYDRAULIC CALCULATION', styles['Title']), Spacer(1, 14), Paragraph(title, styles['Heading2'])]
    for heading, values in [('Inputs', calculation['inputs']), ('Results', calculation['results'])]:
        story += [Spacer(1, 12), Paragraph(heading, styles['Heading3'])]
        data = [[Paragraph(escape(str(k)), styles['Normal']), Paragraph(escape(str(v)), styles['Normal'])] for k,v in values.items()]
        table = Table(data, colWidths=[230, 240], hAlign='LEFT')
        table.setStyle(TableStyle([('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.whitesmoke, colors.white]), ('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8)]))
        story.append(table)
    story += [Spacer(1, 12), Paragraph('Governing relationship', styles['Heading3']), Paragraph(escape(str(calculation['formula'])), styles['Normal']), Spacer(1, 12), Paragraph('Results assume the selected idealized hydraulic model is applicable; confirm field conditions and discharge coefficients before design use.', styles['Italic'])]
    doc.build(story)
    return buffer.getvalue()
