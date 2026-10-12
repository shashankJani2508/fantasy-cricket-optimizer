"""Render backtest_report.md (headings, paragraphs, lists, pipe tables) to a PDF with reportlab."""
import re
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

src, out = sys.argv[1], sys.argv[2]
ss = getSampleStyleSheet()
body = ParagraphStyle("b", parent=ss["Normal"], fontSize=9.5, leading=13, spaceAfter=5)
cell = ParagraphStyle("c", parent=ss["Normal"], fontSize=7.5, leading=9.5)
head = ParagraphStyle("h", parent=cell, fontName="Helvetica-Bold", textColor=colors.white)
H = {1: ParagraphStyle("h1", parent=ss["Title"], fontSize=20, spaceAfter=10, textColor=colors.HexColor("#0b3d2e")),
     2: ParagraphStyle("h2", parent=ss["Heading2"], fontSize=13.5, spaceBefore=12, spaceAfter=6,
                       textColor=colors.HexColor("#0b3d2e")),
     3: ParagraphStyle("h3", parent=ss["Heading3"], fontSize=11, spaceBefore=8, spaceAfter=4)}
PAGE = landscape(A4)
WIDTH = PAGE[0] - 30 * mm


def inline(t):
    t = t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"`(.+?)`", r'<font face="Courier" size="8">\1</font>', t)
    return t


def table(rows):
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [cells[0]] + cells[2:]   # drop the --- separator row
    n = len(cells[0])
    lens = [max(len(r[i]) if i < len(r) else 0 for r in cells) for i in range(n)]
    lens = [min(max(l, 4), 60) for l in lens]
    widths = [WIDTH * l / sum(lens) for l in lens]
    data = [[Paragraph(inline(c), head if i == 0 else cell) for c in r] for i, r in enumerate(cells)]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0b3d2e")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef4f1")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b8c9c1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


story, lines, i = [], open(src, encoding="utf8").read().splitlines(), 0
while i < len(lines):
    ln = lines[i]
    if not ln.strip():
        i += 1
    elif ln.startswith("#"):
        lvl = len(ln) - len(ln.lstrip("#"))
        story.append(Paragraph(inline(ln[lvl:].strip()), H[min(lvl, 3)]))
        i += 1
    elif ln.startswith("|"):
        rows = []
        while i < len(lines) and lines[i].startswith("|"):
            rows.append(lines[i]); i += 1
        story += [table(rows), Spacer(1, 8)]
    elif re.match(r"^(- |\d+\. )", ln):
        numbered = bool(re.match(r"^\d+\. ", ln))
        items = []
        while i < len(lines) and re.match(r"^(- |\d+\. )", lines[i]):
            items.append(ListItem(Paragraph(inline(re.sub(r"^(- |\d+\. )", "", lines[i])), body)))
            i += 1
        story.append(ListFlowable(items, bulletType="1" if numbered else "bullet", leftIndent=14,
                                  bulletFontSize=8))
    else:
        story.append(Paragraph(inline(ln), body)); i += 1


def footer(c, d):
    c.setFont("Helvetica", 7.5); c.setFillColor(colors.grey)
    c.drawString(15 * mm, 8 * mm, "Fantasy Cricket Match Day Optimizer: backtest report (rubric v1)")
    c.drawRightString(PAGE[0] - 15 * mm, 8 * mm, f"Page {d.page}")


SimpleDocTemplate(out, pagesize=PAGE, leftMargin=15 * mm, rightMargin=15 * mm, topMargin=14 * mm,
                  bottomMargin=15 * mm, title="Backtest report: rubric v1").build(
    story, onFirstPage=footer, onLaterPages=footer)
print("wrote", out)
