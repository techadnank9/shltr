"""Damage Evidence Report: /in (case data + photo + 3D room) -> /out/report.pdf.

Inputs in /in:
  report.json   {"case_id", "title", "created", "damages": [{"label", "metric", "cost_usd"}], "total_usd",
                 "range_pct", "threats": [{"kind", "detail"}], "model", "sandboxes": [...], "room_summary"}
  photo.jpg     sanitized photo from the photo sandbox
  room.glb      3D room (metres, y up, camera at origin looking down -z)
  depth.png     colourised depth map
  stats.json    photo sandbox stats
Outputs in /out: report.pdf, report-meta.json {"pages", "bytes", "sha256", "evidence": {...}}
"""
import hashlib
import json
import sys
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import trimesh
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

IN, OUT, TMP = Path("/in"), Path("/out"), Path("/tmp/report")
INK, AMBER, RED, MUTED, LINE = colors.HexColor("#16232A"), colors.HexColor("#A8620B"), colors.HexColor("#B8343A"), colors.HexColor("#55686F"), colors.HexColor("#D3DCDE")


def log(msg: str) -> None:
    print(f"[report] {msg}", flush=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else ""


def render_views(glb: Path) -> list[Path]:
    """Two views of the real 3D room, drawn from its vertices and colours (no GPU needed)."""
    mesh = trimesh.load(glb, force="mesh", process=False)
    v = np.asarray(mesh.vertices)
    # Colour by distance from the camera: reads clearly as 3D (the real photo is on page 1).
    c = plt.cm.viridis((-v[:, 2] - (-v[:, 2]).min()) / np.ptp(-v[:, 2]))[:, :3]
    idx = np.random.default_rng(0).choice(len(v), size=min(len(v), 25000), replace=False)
    v, c = v[idx], c[idx]
    views = []
    for name, elev, azim in (("front", 12, -90), ("side", 20, -55)):
        fig = plt.figure(figsize=(6, 4), dpi=150)
        ax = fig.add_subplot(111, projection="3d")
        ax.scatter(v[:, 0], -v[:, 2], v[:, 1], c=c, s=2.4, linewidths=0, depthshade=False)
        ax.view_init(elev=elev, azim=azim)
        ax.set_box_aspect((np.ptp(v[:, 0]), np.ptp(v[:, 2]), np.ptp(v[:, 1])))
        ax.set_axis_off()
        fig.patch.set_facecolor("white")
        path = TMP / f"view-{name}.png"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.05)
        plt.close(fig)
        views.append(path)
    return views


def image(path: Path, width: float) -> Image:
    from PIL import Image as PILImage
    w, h = PILImage.open(path).size
    return Image(str(path), width=width, height=width * h / w)


def main() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    data = json.loads((IN / "report.json").read_text())
    photo, glb, depth = IN / "photo.jpg", IN / "room.glb", IN / "depth.png"
    stats = json.loads((IN / "stats.json").read_text()) if (IN / "stats.json").exists() else {}
    started = time.time()
    views = render_views(glb) if glb.exists() else []
    log(f"rendered {len(views)} 3D views in {time.time() - started:.1f} s")

    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], fontName="Helvetica-Bold", fontSize=22, textColor=INK, alignment=0, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], fontName="Helvetica-Bold", fontSize=13, textColor=INK, spaceBefore=10, spaceAfter=4)
    body = ParagraphStyle("body", parent=ss["BodyText"], fontName="Helvetica", fontSize=9.5, leading=13, textColor=INK)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10.5, textColor=MUTED)
    mono = ParagraphStyle("mono", parent=small, fontName="Courier", fontSize=7.2, leading=9)

    total = data.get("total_usd") or 0
    rng = data.get("range_pct") or 25
    story = [
        Paragraph("Damage Evidence Report", h1),
        Paragraph(f"<b>{data.get('title', 'Untitled home')}</b> · case {data['case_id']} · {data.get('created', '')}", body),
        Paragraph("Prepared by Shltr for a disaster-aid or insurance claim. Estimates, not an official assessment.", small),
        Spacer(1, 6),
    ]
    summary = Table(
        [["Estimated repair cost", "Damage items", "3D evidence"],
         [f"${total:,.0f}  ±{rng}%", str(len(data.get("damages", []))), f"{stats.get('vertices', '—'):,} points" if isinstance(stats.get("vertices"), int) else "—"]],
        colWidths=[62 * mm, 50 * mm, 60 * mm])
    summary.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica", 8), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONT", (0, 1), (-1, 1), "Helvetica-Bold", 16), ("TEXTCOLOR", (0, 1), (0, 1), AMBER),
        ("LINEBELOW", (0, 1), (-1, 1), 0.6, LINE), ("BOTTOMPADDING", (0, 1), (-1, 1), 8)]))
    story += [summary, Spacer(1, 8)]
    if photo.exists():
        story += [Paragraph("The room", h2), image(photo, 170 * mm)]
    if data.get("room_summary"):
        story += [Spacer(1, 3), Paragraph(data["room_summary"], small)]

    rows = [["#", "Damage", "Measurement", "Estimate"]]
    for i, d in enumerate(data.get("damages", []), 1):
        rows.append([str(i), Paragraph(d.get("label", ""), body), Paragraph(d.get("metric", ""), body), f"${d.get('cost_usd', 0):,.0f}"])
    rows.append(["", Paragraph("<b>Total</b>", body), Paragraph(f"range ±{rng}%", small), f"${total:,.0f}"])
    table = Table(rows, colWidths=[8 * mm, 88 * mm, 46 * mm, 28 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK), ("LINEBELOW", (0, 1), (-1, -2), 0.3, LINE),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK), ("FONT", (3, 1), (3, -1), "Helvetica", 9.5),
        ("FONT", (3, -1), (3, -1), "Helvetica-Bold", 10.5), ("TEXTCOLOR", (3, -1), (3, -1), AMBER),
        ("ALIGN", (3, 0), (3, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TEXTCOLOR", (0, 1), (0, -1), RED)]))
    story += [PageBreak(), Paragraph("Damage found", h2), table]

    if views or depth.exists():
        story += [Paragraph("3D reconstruction", h2),
                  Paragraph("Rebuilt from the photo by a depth model inside a sealed sandbox with no internet access. Colour shows distance from the camera. "
                            "Distances are in metres; the damage areas above were measured on this 3D surface.", small), Spacer(1, 4)]
        cells = [image(p, 84 * mm) for p in views[:2]]
        if cells:
            story.append(Table([cells], colWidths=[86 * mm] * len(cells)))
        if depth.exists():
            story += [Spacer(1, 4), Paragraph("Depth map (warm = near, cool = far)", small), image(depth, 110 * mm)]

    threats = data.get("threats", [])
    if threats:
        story += [Paragraph("Security events during this case", h2),
                  Paragraph("Suspicious links were opened only inside a throwaway sandbox. What they tried, and what happened:", small)]
        for t in threats:
            story.append(Paragraph(f"<font color='#B8343A'><b>{t.get('kind', '').replace('_', ' ').title()}</b></font> · {t.get('detail', '')}", body))

    evidence = {"photo.jpg": sha256(photo), "room.glb": sha256(glb), "depth.png": sha256(depth)}
    story += [PageBreak(), Paragraph("How this report was made", h2),
              Paragraph(f"1. The survivor's upload was opened only inside a throwaway microVM on Vultr with no network. "
                        f"It produced a clean copy of the photo and the 3D room, then was destroyed.<br/>"
                        f"2. {data.get('model', 'The vision model')} on Vultr Serverless Inference listed the visible damage.<br/>"
                        f"3. The model wrote measuring code; a second sandbox ran it on the 3D surface to measure areas and apply repair prices.<br/>"
                        f"4. This PDF was generated in a third sandbox from those results.", body),
              Paragraph("Evidence fingerprints (SHA-256)", h2),
              Paragraph("Anyone can recompute these from the case files to confirm the evidence was not altered.", small)]
    for name, digest in evidence.items():
        if digest:
            story.append(Paragraph(f"{name}  {digest}", mono))
    if data.get("sandboxes"):
        story += [Paragraph("Sandboxes used (all destroyed after use)", h2), Paragraph(", ".join(data["sandboxes"]), mono)]
    story += [Spacer(1, 10), Paragraph(f"Generated {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())} · Shltr · "
                                       "costs are rough averages for planning an aid or insurance claim.", small)]

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, f"Shltr · Damage Evidence Report · case {data['case_id']}")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"page {doc.page}")
        canvas.restoreState()

    out = OUT / "report.pdf"
    doc = SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=18 * mm,
                            title=f"Damage Evidence Report {data['case_id']}", author="Shltr")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    meta = {"pages": doc.page, "bytes": out.stat().st_size, "sha256": sha256(out), "evidence": evidence,
            "seconds": round(time.time() - started, 1)}
    (OUT / "report-meta.json").write_text(json.dumps(meta, indent=2))
    log(f"report.pdf: {meta['pages']} pages, {meta['bytes'] // 1024} KB in {meta['seconds']} s")


if __name__ == "__main__":
    try:
        main()
    except Exception as err:  # noqa: BLE001
        print(f"[report] failed: {type(err).__name__}: {err}", flush=True)
        sys.exit(1)
