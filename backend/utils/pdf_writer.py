from __future__ import annotations

from io import BytesIO
from pathlib import Path

from matplotlib.figure import Figure
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


PAGE_WIDTH, PAGE_HEIGHT = A4


def build_analysis_pdf(
    output_path: str | Path,
    title: str,
    artifact_id: str,
    pages: list[dict],
    generated_at: str | None = None,
    audit_run_id: str | None = None,
) -> str:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    font_names = register_pdf_fonts()
    styles = build_styles(font_names)

    document = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=title,
        author="ORBIS",
    )

    story = []
    for index, page in enumerate(pages):
        story.extend(build_page_story(page, styles))
        if index < len(pages) - 1:
            story.append(PageBreak())

    document.build(
        story,
        onFirstPage=lambda canvas, doc: draw_page_frame(canvas, doc, title, artifact_id, generated_at, audit_run_id, styles),
        onLaterPages=lambda canvas, doc: draw_page_frame(canvas, doc, title, artifact_id, generated_at, audit_run_id, styles),
    )
    return str(target)


def register_pdf_fonts() -> dict[str, str]:
    candidates = [
        ("FatihSans", "C:/Windows/Fonts/arial.ttf"),
        ("FatihSansBold", "C:/Windows/Fonts/arialbd.ttf"),
        ("FatihSansItalic", "C:/Windows/Fonts/ariali.ttf"),
        ("FatihSansBoldItalic", "C:/Windows/Fonts/arialbi.ttf"),
        ("FatihSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        ("FatihSansBold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("FatihSansItalic", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
        ("FatihSansBoldItalic", "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf"),
    ]
    registered = {}
    for name, path in candidates:
        if name in registered:
            continue
        try:
            font_path = Path(path)
            if font_path.exists():
                pdfmetrics.registerFont(TTFont(name, str(font_path)))
                registered[name] = name
        except Exception:
            continue
    if {"FatihSans", "FatihSansBold"}.issubset(registered):
        try:
            pdfmetrics.registerFontFamily(
                "FatihSansFamily",
                normal=registered["FatihSans"],
                bold=registered["FatihSansBold"],
                italic=registered.get("FatihSansItalic", registered["FatihSans"]),
                boldItalic=registered.get("FatihSansBoldItalic", registered["FatihSansBold"]),
            )
            return {"regular": registered["FatihSans"], "bold": registered["FatihSansBold"]}
        except Exception:
            pass
    return {"regular": "Helvetica", "bold": "Helvetica-Bold"}


def build_styles(font_names: dict[str, str]):
    base = getSampleStyleSheet()
    regular = font_names["regular"]
    bold = font_names["bold"]
    base.add(
        ParagraphStyle(
            name="FatihTitle",
            parent=base["Heading1"],
            fontName=bold,
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=8,
        )
    )
    base.add(
        ParagraphStyle(
            name="FatihSection",
            parent=base["Heading2"],
            fontName=bold,
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#111827"),
            spaceBefore=8,
            spaceAfter=6,
        )
    )
    base.add(
        ParagraphStyle(
            name="FatihBody",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9.5,
            leading=14,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        )
    )
    base.add(
        ParagraphStyle(
            name="FatihSmall",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#475569"),
            spaceAfter=4,
        )
    )
    base.add(
        ParagraphStyle(
            name="FatihCallout",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#0F172A"),
            backColor=colors.HexColor("#F8FAFC"),
            borderPadding=6,
            borderColor=colors.HexColor("#CBD5E1"),
            borderWidth=0.6,
            spaceAfter=8,
        )
    )
    return base


def draw_page_frame(canvas, doc, title: str, artifact_id: str, generated_at: str | None, audit_run_id: str | None, styles):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, PAGE_HEIGHT - 14 * mm, PAGE_WIDTH - doc.rightMargin, PAGE_HEIGHT - 14 * mm)
    canvas.line(doc.leftMargin, 12 * mm, PAGE_WIDTH - doc.rightMargin, 12 * mm)
    canvas.setFont(styles["FatihSmall"].fontName, 8)
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.drawString(doc.leftMargin, PAGE_HEIGHT - 10 * mm, title)
    canvas.drawRightString(PAGE_WIDTH - doc.rightMargin, PAGE_HEIGHT - 10 * mm, artifact_id)
    footer = f"Sayfa {canvas.getPageNumber()}"
    if generated_at:
        footer = f"{generated_at} | {footer}"
    if audit_run_id:
        footer = f"{footer} | {audit_run_id[:12]}"
    canvas.drawString(doc.leftMargin, 7 * mm, footer)
    canvas.restoreState()


def build_page_story(page: dict, styles):
    story = [Paragraph(page.get("title", ""), styles["FatihTitle"])]
    if page.get("subtitle"):
        story.append(Paragraph(page["subtitle"], styles["FatihSmall"]))
        story.append(Spacer(1, 4))
    for block in page.get("blocks", []):
        block_type = block.get("type")
        if block_type == "paragraph":
            for paragraph in split_paragraphs(block.get("text", "")):
                story.append(Paragraph(paragraph, styles["FatihBody"]))
        elif block_type == "callout":
            story.append(Paragraph(block.get("text", ""), styles["FatihCallout"]))
        elif block_type == "metrics":
            story.append(build_metric_table(block.get("items", []), styles))
            story.append(Spacer(1, 8))
        elif block_type == "table":
            if block.get("title"):
                story.append(Paragraph(block["title"], styles["FatihSection"]))
            story.append(build_data_table(block.get("headers", []), block.get("rows", []), styles))
            story.append(Spacer(1, 8))
        elif block_type == "figure":
            figure = block.get("figure")
            if isinstance(figure, Figure):
                story.append(matplotlib_figure_to_image(figure))
                story.append(Spacer(1, 8))
        elif block_type == "kv_table":
            story.append(build_key_value_table(block.get("items", []), styles))
            story.append(Spacer(1, 8))
    return story


def build_metric_table(items: list[dict], styles):
    if not items:
        return Paragraph("Bu sayfa icin metrik bulunamadi.", styles["FatihBody"])
    data = []
    row = []
    for index, item in enumerate(items, start=1):
        value = item.get("value") if item.get("value") not in (None, "") else "-"
        row.append(Paragraph(f"<b>{item.get('label', '-')}</b><br/>{value}", styles["FatihBody"]))
        if index % 2 == 0:
            data.append(row)
            row = []
    if row:
        while len(row) < 2:
            row.append(Paragraph("", styles["FatihBody"]))
        data.append(row)
    table = Table(data, colWidths=[85 * mm, 85 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def build_key_value_table(items: list[tuple[str, str]] | list[list[str]], styles):
    rows = [["Alan", "Deger"]]
    for item in items:
        if isinstance(item, tuple):
            rows.append([item[0], item[1]])
        else:
            rows.append([item[0], item[1]])
    return build_data_table(rows[0], rows[1:], styles)


def build_data_table(headers: list[str], rows: list[list[str]], styles):
    if not headers:
        headers = ["Bilgi", "Deger"]
    table_data = [[Paragraph(f"<b>{header}</b>", styles["FatihBody"]) for header in headers]]
    for row in rows or [["-", "-"]]:
        padded = list(row) + [""] * max(0, len(headers) - len(row))
        table_data.append([Paragraph(str(cell), styles["FatihBody"]) for cell in padded[: len(headers)]])
    column_width = (PAGE_WIDTH - 36 * mm) / max(len(headers), 1)
    table = Table(table_data, repeatRows=1, colWidths=[column_width] * len(headers), hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E2E8F0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def split_paragraphs(text: str) -> list[str]:
    paragraphs = [part.strip() for part in str(text or "").split("\n\n") if part.strip()]
    if paragraphs:
        return paragraphs
    cleaned = str(text or "").strip()
    return [cleaned] if cleaned else []


def matplotlib_figure_to_image(figure: Figure):
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=180, bbox_inches="tight", facecolor="white")
    buffer.seek(0)
    return Image(buffer, width=170 * mm, height=92 * mm)
