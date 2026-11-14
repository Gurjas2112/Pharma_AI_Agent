"""Report Generator agent: PDF (ReportLab + charts) and Excel (openpyxl)."""

from __future__ import annotations

import io
import re
from datetime import UTC, datetime
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from repurpora.report.charts import render

TEAL = colors.HexColor("#0E7C86")
INK = colors.HexColor("#1B2430")
DECISION_COLORS = {"GO": "#2E7D32", "PARTIAL_GO": "#F2A541", "NO_GO": "#C8553D"}


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle("H", parent=ss["Heading2"], textColor=TEAL, spaceBefore=10, spaceAfter=4))
    ss.add(ParagraphStyle("B", parent=ss["BodyText"], fontSize=9, leading=12.5, textColor=INK))
    ss.add(ParagraphStyle("S", parent=ss["BodyText"], fontSize=7.5, leading=10, textColor=colors.grey))
    ss.add(ParagraphStyle("Cell", parent=ss["BodyText"], fontSize=7, leading=8.5))
    return ss


def _md_inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)\*", r"<i>\1</i>", text)
    text = re.sub(r"\[(E\d+)\]", r"<font color='#0E7C86'>[\1]</font>", text)
    return text


def _markdown_flow(md: str, ss) -> list:
    flow = []
    for block in re.split(r"\n{2,}", md.strip()):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines or all(ln.strip().startswith("|") for ln in lines):
            continue  # markdown tables are rendered from structured data instead
        for ln in lines:
            s = ln.strip()
            if s.startswith("#"):
                flow.append(Paragraph(_md_inline(s.lstrip("# ")), ss["H"]))
            elif s.startswith(("- ", "* ", "• ")):
                flow.append(Paragraph("• " + _md_inline(s[2:]), ss["B"]))
            elif re.match(r"^\d+\.\s", s):
                flow.append(Paragraph(_md_inline(s), ss["B"]))
            elif not s.startswith("|"):
                flow.append(Paragraph(_md_inline(s), ss["B"]))
        flow.append(Spacer(1, 4))
    return flow


def _table(t: dict[str, Any], ss) -> Table:
    cols = t["columns"]
    rows = [[Paragraph(f"<b>{c}</b>", ss["Cell"]) for c in cols]]
    for r in t["rows"][:12]:
        rows.append([Paragraph(_md_inline(str(v if v is not None else "-"))[:140], ss["Cell"]) for v in r])
    width = 17.5 * cm / max(len(cols), 1)
    tbl = Table(rows, colWidths=[width] * len(cols), repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E3F2F3")),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D6D8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAFA")]),
    ]))
    return tbl


def build_pdf(ctx: dict[str, Any]) -> bytes:
    ss = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm,
                            topMargin=1.4 * cm, bottomMargin=1.4 * cm,
                            title=f"Repurpora report {ctx['report_id']}", author="Repurpora · Lazarus Graph")
    plan, scores = ctx["plan"], ctx["scores"]
    decision = scores.get("decision", "PARTIAL_GO")
    flow: list = [
        Paragraph("<font size=18 color='#0E7C86'><b>Repurpora</b></font>"
                  "<font size=10 color='#888888'>  ·  Lazarus Graph innovation brief</font>", ss["Title"]),
        Paragraph(f"Report <b>{ctx['report_id']}</b> · generated {datetime.now(UTC):%d %b %Y %H:%M} UTC", ss["S"]),
        Spacer(1, 6),
        Paragraph(f"<b>Query:</b> {_md_inline(ctx['query'])}", ss["B"]),
        Paragraph(f"<b>Molecule:</b> {(plan.get('molecule') or '-').title()} · <b>Indication focus:</b> "
                  f"{plan.get('indication') or scores.get('best_opportunity') or '-'} · <b>Region:</b> "
                  f"{plan.get('region') or '-'}", ss["B"]),
        Spacer(1, 6),
    ]
    dc = DECISION_COLORS.get(decision, "#555555")
    kpi = Table([[
        Paragraph(f"<font color='{dc}' size=14><b>{decision.replace('_', '-')}</b></font><br/>"
                  f"<font size=7>rule-based decision · confidence {scores.get('confidence', '-')}%</font>", ss["B"]),
        Paragraph(f"<font size=14><b>{scores.get('ml_probability', 0):.0%}</b></font><br/>"
                  f"<font size=7>ML success probability ({scores.get('ml_model', '-')}, AUC "
                  f"{scores.get('ml_auc', '-')})</font>", ss["B"]),
        Paragraph(f"<font size=14><b>{ctx.get('coverage', 0):.0%}</b></font><br/>"
                  f"<font size=7>evidence coverage (claims cited)</font>", ss["B"]),
    ]], colWidths=[5.8 * cm] * 3)
    kpi.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, TEAL), ("INNERGRID", (0, 0), (-1, -1), 0.25, TEAL),
                             ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3FAFA"))]))
    flow += [kpi, Spacer(1, 8)]
    flow += _markdown_flow(ctx["synthesis"], ss)

    # worker sections
    for r in ctx["results"]:
        if r.get("error") and not r.get("tables"):
            continue
        sect = [Paragraph(f"{r['agent'].replace('_', ' ').title()} agent", ss["H"])]
        if r.get("summary"):
            sect += _markdown_flow(r["summary"], ss)
        for t in r.get("tables", [])[:2]:
            sect += [Paragraph(f"<b>{t['title']}</b>", ss["S"]), _table(t, ss), Spacer(1, 4)]
        flow.append(KeepTogether(sect[:3]))
        flow += sect[3:]
        for ch in r.get("charts", [])[:2]:
            if png := render(ch):
                flow.append(Image(io.BytesIO(png), width=15 * cm, height=7.5 * cm))
    # ML explainability
    if scores.get("ml_drivers"):
        flow.append(Paragraph("ML opportunity score - top drivers", ss["H"]))
        flow.append(_table({"columns": ["feature", "Δ probability vs median"],
                            "rows": [[f, f"{v:+.3f}"] for f, v in scores["ml_drivers"]]}, ss))
    # evidence appendix
    flow += [PageBreak(), Paragraph("Evidence register", ss["H"]),
             Paragraph("Every cited claim maps to an evidence record with source, trust tier and content hash. "
                       "Synthetic sources are mock data per the problem statement.", ss["S"])]
    flow.append(_table({"columns": ["id", "agent", "source", "trust", "title / url", "sha256"],
                        "rows": [[e["id"], e["agent"], e["source"], e["trust"],
                                  (e.get("url") or e["title"])[:90], e["sha256"]] for e in ctx["evidence"][:40]]}, ss))
    flow += [Spacer(1, 8), Paragraph(
        "Decision support only - not medical, legal or regulatory advice. Validate IP findings with counsel "
        "and clinical claims with primary literature.", ss["S"])]
    doc.build(flow)
    return buf.getvalue()


def build_excel(ctx: dict[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Summary"
    head = Font(bold=True, color="FFFFFF")
    fill = PatternFill("solid", fgColor="0E7C86")
    s = ctx["scores"]
    for row in [["Report", ctx["report_id"]], ["Query", ctx["query"]],
                ["Decision", s.get("decision")], ["Confidence", s.get("confidence")],
                ["ML probability", s.get("ml_probability")], ["Evidence coverage", ctx.get("coverage")]]:
        ws.append(row)
    for r in ctx["results"]:
        for t in r.get("tables", []):
            name = re.sub(r"[^A-Za-z0-9 ]", "", f"{r['agent'][:8]} {t['title']}")[:31]
            sh = wb.create_sheet(name or "data")
            sh.append(t["columns"])
            for c in sh[1]:
                c.font, c.fill = head, fill
            for row in t["rows"]:
                sh.append([v if isinstance(v, (int, float, str)) or v is None else str(v) for v in row])
    ev = wb.create_sheet("Evidence")
    ev.append(["id", "agent", "source", "trust", "title", "url", "sha256"])
    for e in ctx["evidence"]:
        ev.append([e["id"], e["agent"], e["source"], e["trust"], e["title"], e.get("url"), e["sha256"]])
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
