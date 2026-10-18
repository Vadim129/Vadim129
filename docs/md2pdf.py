"""Markdown -> PDF for the animation guide (reportlab, PT Sans/PT Serif).

Usage: python3 docs/md2pdf.py ANIMATION_GUIDE.md docs/ANIMATION_GUIDE.pdf
"""
from __future__ import annotations

import os
import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, HRFlowable, PageBreak,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle,
                                XPreformatted)

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.path.join(HERE, "fonts")

INK = colors.HexColor("#211d1b")
WINE = colors.HexColor("#7b2340")
MUTED = colors.HexColor("#6d6a67")
RULE = colors.HexColor("#d9ccbe")
CREAM = colors.HexColor("#f8f2ea")
CODE_BG = colors.HexColor("#f4efe9")

PAGE_W, PAGE_H = A4
MARGIN_X = 20 * mm
MARGIN_T = 20 * mm
MARGIN_B = 20 * mm
FRAME_W = PAGE_W - 2 * MARGIN_X

pdfmetrics.registerFont(TTFont("Body", os.path.join(FONTS, "PT_Sans-Web-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Body-Bold", os.path.join(FONTS, "PT_Sans-Web-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Body-Italic", os.path.join(FONTS, "PT_Sans-Web-Italic.ttf")))
pdfmetrics.registerFont(TTFont("Head", os.path.join(FONTS, "PT_Serif-Web-Bold.ttf")))
pdfmetrics.registerFont(TTFont("Head-Reg", os.path.join(FONTS, "PT_Serif-Web-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Arrow", os.path.join(FONTS, "NotoSansSymbols.ttf")))
pdfmetrics.registerFont(TTFont("Box", os.path.join(FONTS, "NotoSansSymbols2-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Mono", os.path.join(FONTS, "PTM55FT.ttf")))
pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold", italic="Body-Italic",
                              boldItalic="Body-Bold")

S = {
    "h1": ParagraphStyle("h1", fontName="Head", fontSize=26, leading=30, textColor=INK,
                         spaceAfter=8),
    "sub": ParagraphStyle("sub", fontName="Body", fontSize=10.4, leading=15.4, textColor=MUTED),
    "kicker": ParagraphStyle("kicker", fontName="Body-Bold", fontSize=8.0, leading=10,
                             textColor=WINE, spaceAfter=9),
    "h2": ParagraphStyle("h2", fontName="Head", fontSize=15, leading=18, textColor=WINE,
                         spaceBefore=15, spaceAfter=6, keepWithNext=1),
    "h3": ParagraphStyle("h3", fontName="Body-Bold", fontSize=10.6, leading=13.5, textColor=INK,
                         spaceBefore=10, spaceAfter=3, keepWithNext=1),
    "p": ParagraphStyle("p", fontName="Body", fontSize=9.6, leading=13.8, textColor=INK,
                        alignment=TA_LEFT, spaceAfter=5.5),
    "li": ParagraphStyle("li", fontName="Body", fontSize=9.5, leading=13.2, textColor=INK,
                         leftIndent=16, bulletIndent=0, spaceAfter=2.6),
    "lic": ParagraphStyle("lic", fontName="Body", fontSize=9.5, leading=13.2, textColor=INK,
                          leftIndent=16, bulletIndent=0, spaceAfter=2.6,
                          bulletFontName="Box", bulletFontSize=8),
    "quote": ParagraphStyle("quote", fontName="Body-Italic", fontSize=9.4, leading=13.6,
                            textColor=colors.HexColor("#5a5551"), leftIndent=6),
    "cell": ParagraphStyle("cell", fontName="Body", fontSize=8.1, leading=10.4, textColor=INK),
    "cellh": ParagraphStyle("cellh", fontName="Body-Bold", fontSize=8.1, leading=10.4,
                            textColor=INK),
    "code": ParagraphStyle("code", fontName="Mono", fontSize=7.9, leading=10.4,
                           textColor=colors.HexColor("#3b3733")),
    "toc": ParagraphStyle("toc", fontName="Body", fontSize=9.2, leading=12.9, textColor=INK,
                          leftIndent=13, bulletIndent=0),
    "pull": ParagraphStyle("pull", fontName="Head-Reg", fontSize=14.5, leading=19,
                           textColor=WINE),
    "caption": ParagraphStyle("caption", fontName="Body-Italic", fontSize=8.6, leading=11.6,
                              textColor=MUTED, spaceBefore=12),
}


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]+)`",
                  r'<font name="Mono" size="8.3" color="#8a4a2c">\1</font>', text)
    text = text.replace("\u2192", '<font name="Arrow">\u2192</font>')
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    return text


def col_widths(rows, total):
    n = max(len(r) for r in rows)
    weights = []
    for c in range(n):
        longest = max((len(r[c]) if c < len(r) else 0) for r in rows)
        weights.append(min(max(longest, 6), 70) ** 0.75)
    s = sum(weights)
    widths = [total * w / s for w in weights]
    # keep narrow pages readable
    floor = 34
    for k, w in enumerate(widths):
        if w < floor:
            widths[k] = floor
    scale = total / sum(widths)
    return [w * scale for w in widths]


def table_flow(rows):
    head, body = rows[0], rows[1:]
    data = [[Paragraph(inline(c), S["cellh"]) for c in head]]
    for r in body:
        r = list(r) + [""] * (len(head) - len(r))
        data.append([Paragraph(inline(c), S["cell"]) for c in r])
    t = Table(data, colWidths=col_widths(rows, FRAME_W), repeatRows=1, hAlign="LEFT")
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), CREAM),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, RULE),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2d8cc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3.4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.6),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#fcf9f5")))
    t.setStyle(TableStyle(style))
    return [Spacer(1, 4), t, Spacer(1, 8)]


def quote_flow(text):
    t = Table([[Paragraph(inline(text), S["quote"])]], colWidths=[FRAME_W], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, WINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbf7f2")),
    ]))
    return [Spacer(1, 2), t, Spacer(1, 8)]


def code_flow(text):
    pre = XPreformatted(text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
                        S["code"])
    t = Table([[pre]], colWidths=[FRAME_W], hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#e4d9cc")),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return [t, Spacer(1, 9)]


def parse(lines):
    """Markdown subset -> list of flowables."""
    story, i, quote = [], 0, []

    def flush():
        nonlocal quote
        if quote:
            story.extend(quote_flow(" ".join(quote)))
            quote = []

    while i < len(lines):
        stripped = lines[i].strip()

        if stripped.startswith("```"):
            flush()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            story.extend(code_flow("\n".join(buf)))
            i += 1
            continue

        if stripped.startswith("# ") or stripped.startswith("## "):
            flush()
            level = 1 if stripped.startswith("# ") else 2
            text = stripped[level + 1:].strip()
            if level == 2:
                story.append(Paragraph(inline(text), S["h2"]))
            i += 1
            continue

        if stripped.startswith("### "):
            flush()
            story.append(Paragraph(inline(stripped[4:].strip()), S["h3"]))
            i += 1
            continue

        if stripped.startswith(">"):
            quote.append(stripped.lstrip(">").strip())
            i += 1
            continue

        if stripped.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                story.extend(table_flow(rows))
            continue

        if re.match(r"^[-*] \[[ x]\] ", stripped):
            flush()
            story.append(Paragraph(inline(stripped[6:].strip()), S["lic"], bulletText="\u2610"))
            i += 1
            continue

        if re.match(r"^[-*] ", stripped):
            flush()
            story.append(Paragraph(inline(stripped[2:].strip()), S["li"], bulletText="\u2022"))
            i += 1
            continue

        m = re.match(r"^(\d+)\.\s+(.*)$", stripped)
        if m:
            flush()
            story.append(Paragraph(inline(m.group(2)), S["li"], bulletText=f"{m.group(1)}."))
            i += 1
            continue

        if stripped == "---":
            flush()
            story.append(Spacer(1, 6))
            i += 1
            continue

        if not stripped:
            flush()
            i += 1
            continue

        flush()
        buf = [stripped]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (not nxt or nxt.startswith(("#", ">", "|", "```", "- ", "* ", "---"))
                    or re.match(r"^\d+\.\s", nxt)):
                break
            buf.append(nxt)
            i += 1
        story.append(Paragraph(inline(" ".join(buf)), S["p"]))

    flush()
    return story


def build(src, out):
    lines = open(src, encoding="utf-8").read().splitlines()

    title = "Оживление персонажа"
    intro, body = [], []
    seen_title = False
    in_intro = True
    for line in lines:
        s = line.strip()
        if s.startswith("# ") and not seen_title:
            title = s[2:].strip()
            seen_title = True
            continue
        if in_intro and s.startswith(">"):
            intro.append(s.lstrip(">").strip())
            continue
        if s.startswith("## "):
            in_intro = False
        body.append(line)

    toc = [l.strip()[3:].strip() for l in body if l.strip().startswith("## ")]

    cover = [Spacer(1, 52), Paragraph("БАЗОВОЕ РУКОВОДСТВО", S["kicker"]),
             Paragraph(title, S["h1"])]
    if intro:
        cover += [Spacer(1, 8), Paragraph(inline(" ".join(intro)), S["sub"])]

    cover += [Spacer(1, 14),
              HRFlowable(width="100%", thickness=0.6, color=RULE, spaceAfter=14),
              Paragraph("Движение — это не перемещение объекта в кадре.<br/>"
                        "Это смена позы во времени.", S["pull"]),
              Spacer(1, 26), Paragraph("Содержание", S["h3"])]

    half = (len(toc) + 1) // 2
    cols = []
    for part in (toc[:half], toc[half:]):
        flow = [Paragraph(inline(t), S["toc"], bulletText="\u00b7") for t in part]
        cols.append(flow if flow else [Paragraph("", S["toc"])])
    toc_table = Table([cols], colWidths=[FRAME_W / 2 - 8, FRAME_W / 2 - 8], hAlign="LEFT")
    toc_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("LEFTPADDING", (1, 0), (1, 0), 16),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    cover.append(toc_table)
    cover.append(Spacer(1, 34))

    how = [
        ("0–3", "База: кто персонаж, что делает, что чувствует, из чего собирается поза."),
        ("4–12", "Приёмы и параметры: принципы, тайминг, циклы, вес, лицо, музыка, камера."),
        ("13–17", "Ошибки, процесс работы, приёмка, словарь и шаблон задачи."),
    ]
    rows = [[Paragraph(k, S["cellh"]), Paragraph(v, S["cell"])] for k, v in how]
    how_table = Table(rows, colWidths=[42, FRAME_W - 42], hAlign="LEFT")
    how_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbf7f2")),
        ("LINEBEFORE", (0, 0), (0, -1), 2.2, WINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    cover.append(how_table)
    cover.append(Spacer(1, 18))
    cover.append(Paragraph("Документ универсальный: персонаж, стиль, инструмент и формат задаются "
                           "отдельно.", S["caption"]))
    cover.append(PageBreak())

    doc = BaseDocTemplate(out, pagesize=A4, leftMargin=MARGIN_X, rightMargin=MARGIN_X,
                          topMargin=MARGIN_T, bottomMargin=MARGIN_B,
                          title=title, author="", creator="md2pdf")
    frame = Frame(MARGIN_X, MARGIN_B, FRAME_W, PAGE_H - MARGIN_T - MARGIN_B, id="body",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def page(canv, d):
        canv.saveState()
        canv.setFont("Body", 7.6)
        canv.setFillColor(MUTED)
        canv.drawString(MARGIN_X, PAGE_H - 12 * mm, "Оживление персонажа · базовое руководство")
        canv.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 12 * mm, str(canv.getPageNumber()))
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.4)
        canv.line(MARGIN_X, PAGE_H - 14 * mm, PAGE_W - MARGIN_X, PAGE_H - 14 * mm)
        canv.line(MARGIN_X, 14 * mm, PAGE_W - MARGIN_X, 14 * mm)
        canv.setFont("Body", 7.2)
        canv.drawCentredString(PAGE_W / 2, 10 * mm, "агент · инструкция")
        canv.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=page)])
    doc.build(cover + parse(body))
    print("wrote", out)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2])
