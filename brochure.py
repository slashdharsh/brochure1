"""
Phase 2: Drug Brochure PDF Generator (v3 — spacing fixed, panels filled)
"""

import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# ── Palette ────────────────────────────────────────────────────────────────────
NAVY       = colors.HexColor("#1B3A6B")
TEAL       = colors.HexColor("#0D7E83")
TEAL_LIGHT = colors.HexColor("#D6EEEF")
AMBER      = colors.HexColor("#E8A020")
AMBER_LIGHT= colors.HexColor("#FDF3E0")
WHITE      = colors.white
OFF_WHITE  = colors.HexColor("#F7F9FC")
GREY_BG    = colors.HexColor("#EEF1F5")
DARK_TEXT  = colors.HexColor("#1E1E1E")
MID_TEXT   = colors.HexColor("#3A3A3A")
MUTED_TEXT = colors.HexColor("#777777")
LIGHT_LINE = colors.HexColor("#C8D4E0")

# ── Page / panel geometry ──────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(A4)
P      = PAGE_W / 3          # panel width ≈ 280.63 pt
M      = 10 * mm             # inner margin
BODY_W = P - 2 * M          # usable text width per panel
BAR_H  = 6 * mm             # section header bar height


# ══════════════════════════════════════════════════════════════════════════════
#  Drawing primitives
# ══════════════════════════════════════════════════════════════════════════════

def _wrap(c, text, x, y, max_w, font, size, leading,
          colour=MID_TEXT, max_lines=99):
    """Word-wrap text. Returns y after last line."""
    c.setFont(font, size)
    c.setFillColor(colour)
    words = text.split()
    line  = ""
    drawn = 0
    for word in words:
        test = f"{line} {word}".strip()
        if c.stringWidth(test, font, size) <= max_w:
            line = test
        else:
            if drawn >= max_lines:
                break
            if line:
                c.drawString(x, y, line)
                y    -= leading
                drawn += 1
            line = word
    if line and drawn < max_lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def _section_bar(c, title, x, y, w, bg=TEAL, fg=WHITE):
    """Draw filled header bar. Returns y BELOW bar with proper gap."""
    c.setFillColor(bg)
    c.rect(x, y - BAR_H, w, BAR_H, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(fg)
    # vertically centre text in bar
    c.drawString(x + 5, y - BAR_H + (BAR_H - 7.5) / 2 + 1, title.upper())
    return y - BAR_H - 10  # clear below bar: font cap-height + buffer


def _section(c, title, text, x, y, w, font_size=8, leading=11.5,
             max_lines=99, bar_bg=TEAL, bar_fg=WHITE, indent=4):
    """Full section: bar + body. Returns y after content + bottom gap."""
    y = _section_bar(c, title, x, y, w, bg=bar_bg, fg=bar_fg)
    y = _wrap(c, text, x + indent, y, w - indent - 2,
              "Helvetica", font_size, leading,
              colour=MID_TEXT, max_lines=max_lines)
    return y - 5   # gap below section


def _panel_header(c, title, subtitle, x0, w, bg=NAVY, h=14*mm):
    """Coloured top header across full panel height h. Returns y below."""
    c.setFillColor(bg)
    c.rect(x0, PAGE_H - h, w, h, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(WHITE)
    c.drawCentredString(x0 + w/2, PAGE_H - h + h*0.55, title)
    if subtitle:
        c.setFont("Helvetica", 7.5)
        c.setFillColor(colors.HexColor("#AACFCF"))
        c.drawCentredString(x0 + w/2, PAGE_H - h + h*0.2, subtitle)
    return PAGE_H - h - 12  # clear below header


def _divider(c, x, y, w, colour=LIGHT_LINE):
    c.setStrokeColor(colour)
    c.setLineWidth(0.5)
    c.line(x, y, x + w, y)
    return y - 4


def _pill_badge(c, text, cx, y, bg=TEAL, fg=WHITE, font_size=7.5):
    """Draw a rounded pill badge centred at cx."""
    tw  = c.stringWidth(text, "Helvetica", font_size)
    bw  = tw + 18
    bx  = cx - bw / 2
    c.setFillColor(bg)
    c.roundRect(bx, y - 4, bw, 13, 4, fill=1, stroke=0)
    c.setFont("Helvetica", font_size)
    c.setFillColor(fg)
    c.drawCentredString(cx, y, text)
    return y - 4 - 13   # bottom of badge


def _key_value_row(c, label, value, x, y, w, label_w=70):
    """Draw a small label: value row with a light separator."""
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(TEAL)
    c.drawString(x, y, label)
    c.setFont("Helvetica", 7.5)
    c.setFillColor(MID_TEXT)
    # wrap value in remaining width
    val_x = x + label_w
    val_w = w - label_w
    words = value.split()
    line  = ""
    first = True
    for word in words:
        test = f"{line} {word}".strip()
        if c.stringWidth(test, "Helvetica", 7.5) <= val_w:
            line = test
        else:
            c.drawString(val_x, y, line)
            y   -= 10
            line = word
            first = False
    if line:
        c.drawString(val_x, y, line)
        y -= 10
    return y - 2


def _info_card(c, lines, x, y, w, bg=OFF_WHITE, pad=6):
    """Draw a shaded info card containing list of (bold_label, text) tuples."""
    font_size = 7.5
    line_h    = 12
    # total height: top pad + each line + bottom pad
    total_h   = pad + len(lines) * line_h + pad
    card_top  = y
    card_bot  = y - total_h
    c.setFillColor(bg)
    c.roundRect(x, card_bot, w, total_h, 4, fill=1, stroke=0)
    # first baseline: inside top pad, leaving room for cap-height
    # cap-height of 7.5pt Helvetica ≈ 5.4pt; baseline = card_top - pad - cap_h
    cy = card_top - pad - font_size * 0.72
    for label, text in lines:
        c.setFont("Helvetica-Bold", font_size)
        c.setFillColor(NAVY)
        c.drawString(x + pad, cy, label)
        lw = c.stringWidth(label, "Helvetica-Bold", font_size)
        c.setFont("Helvetica", font_size)
        c.setFillColor(MID_TEXT)
        # truncate value to fit remaining width
        val_x = x + pad + lw + 4
        val_w = w - pad - lw - 8
        val   = text
        while val and c.stringWidth(val, "Helvetica", font_size) > val_w:
            val = val[:val.rfind(" ")] if " " in val else val[:-1]
        c.drawString(val_x, cy, val)
        cy -= line_h
    return card_bot - 6


def _dot_list(c, items, x, y, w, font_size=8, leading=11):
    """Draw a bulleted list of strings. Dot anchored to first-line cap centre."""
    for item in items:
        # dot centre = baseline + half cap-height of font
        dot_cy = y - font_size * 0.5 + font_size * 0.72 / 2
        c.setFillColor(TEAL)
        c.circle(x + 4, dot_cy, 2, fill=1, stroke=0)
        y = _wrap(c, item, x + 13, y, w - 13,
                  "Helvetica", font_size, leading,
                  colour=MID_TEXT, max_lines=3)
        y -= 4   # increased gap between bullets
    return y


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 1 — Outside spread
#  [BACK (x=0)] [SPINE (x=P)] [FRONT COVER (x=2P)]
# ══════════════════════════════════════════════════════════════════════════════

def _front_cover(c, data):
    x0 = P * 2

    # Background
    c.setFillColor(NAVY)
    c.rect(x0, 0, P, PAGE_H, fill=1, stroke=0)

    # Teal decorative circle top-right
    c.setFillColor(TEAL)
    c.circle(x0 + P + 10, PAGE_H + 10, 120, fill=1, stroke=0)

    # Teal arc bottom-left
    c.setFillColor(colors.HexColor("#0A6469"))
    c.circle(x0, 0, 70, fill=1, stroke=0)

    # Amber accent line
    c.setFillColor(AMBER)
    c.rect(x0 + M, PAGE_H * 0.37, P - 2*M, 2.5, fill=1, stroke=0)

    # Drug name
    name = data.get("drug_name", "Drug")
    c.setFont("Helvetica-Bold", 30)
    c.setFillColor(WHITE)
    tw = c.stringWidth(name, "Helvetica-Bold", 30)
    c.drawString(x0 + (P - tw)/2, PAGE_H * 0.56, name)

    # Generic name
    generic = data.get("generic_name", "")
    if generic and generic.lower() != name.lower():
        c.setFont("Helvetica-Oblique", 9.5)
        c.setFillColor(colors.HexColor("#AACFCF"))
        tw2 = c.stringWidth(generic, "Helvetica-Oblique", 9.5)
        c.drawString(x0 + (P - tw2)/2, PAGE_H * 0.51, generic)

    # Drug class badge
    dc = data.get("drug_class", "")[:42]
    _pill_badge(c, dc, x0 + P/2, PAGE_H * 0.43)

    # Quick facts strip — 3 mini items
    strip_y = PAGE_H * 0.29
    c.setFillColor(colors.HexColor("#152E56"))
    c.rect(x0 + M, strip_y - 28, P - 2*M, 32, fill=1, stroke=0)

    facts = [
        ("Route", "Oral"),
        ("Class", data.get("drug_class", "—")[:22]),
        ("Rx Only", "Yes"),
    ]
    col_w = (P - 2*M) / 3
    for i, (lbl, val) in enumerate(facts):
        cx = x0 + M + col_w * i + col_w/2
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(AMBER)
        lw = c.stringWidth(lbl, "Helvetica-Bold", 6.5)
        c.drawString(cx - lw/2, strip_y - 10, lbl)
        c.setFont("Helvetica", 6.5)
        c.setFillColor(WHITE)
        vw = c.stringWidth(val, "Helvetica", 6.5)
        c.drawString(cx - vw/2, strip_y - 21, val)

    # Vertical separator lines in strip
    for i in [1, 2]:
        c.setStrokeColor(colors.HexColor("#2A4F8A"))
        c.setLineWidth(0.5)
        sx = x0 + M + col_w * i
        c.line(sx, strip_y - 26, sx, strip_y - 2)

    # Manufacturer
    mfr = data.get("manufacturer", "")
    if len(mfr) > 50: mfr = mfr[:47] + "..."
    c.setFont("Helvetica", 6.5)
    c.setFillColor(MUTED_TEXT)
    c.drawCentredString(x0 + P/2, 22, f"Mfd by  {mfr}")

    # Footer tag
    tag = "PRESCRIBING INFORMATION BROCHURE"
    c.setFont("Helvetica-Bold", 6)
    c.setFillColor(AMBER)
    tw3 = c.stringWidth(tag, "Helvetica-Bold", 6)
    c.drawString(x0 + (P - tw3)/2, 10, tag)


def _back_panel(c, data):
    x0 = 0

    c.setFillColor(GREY_BG)
    c.rect(x0, 0, P, PAGE_H, fill=1, stroke=0)

    # Teal top bar
    c.setFillColor(NAVY)
    c.rect(x0, PAGE_H - 14*mm, P, 14*mm, fill=1, stroke=0)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(WHITE)
    c.drawCentredString(x0 + P/2, PAGE_H - 14*mm + 6*mm, data.get("drug_name",""))
    c.setFont("Helvetica", 7.5)
    c.setFillColor(colors.HexColor("#AACFCF"))
    c.drawCentredString(x0 + P/2, PAGE_H - 14*mm + 2.5*mm, "Product Information")

    y = PAGE_H - 14*mm - 8

    # Brand names
    brands = data.get("brand_names", [])
    if brands:
        y = _section(c, "Brand / Trade Names",
                     "  |  ".join(brands[:5]),
                     x0+M, y, BODY_W, max_lines=2, bar_bg=TEAL)

    y = _section(c, "How Supplied",
                 data.get("how_supplied", "See package insert."),
                 x0+M, y, BODY_W, max_lines=5, bar_bg=TEAL)

    y = _section(c, "Storage & Handling",
                 data.get("storage", "Store per manufacturer guidelines."),
                 x0+M, y, BODY_W, max_lines=4, bar_bg=TEAL)

    y = _divider(c, x0+M, y, BODY_W)

    # ── Extra: Key drug facts info card ───────────────────────────────────────
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(NAVY)
    c.drawString(x0+M, y, "KEY DRUG FACTS")
    y -= 14

    facts_lines = [
        ("Generic Name: ", data.get("generic_name","—")[:35]),
        ("Drug Class: ",   data.get("drug_class","—")[:35]),
        ("Manufacturer: ", data.get("manufacturer","—")[:30]),
        ("Route: ",        "Oral"),
        ("Rx Status: ",    "Prescription Only"),
    ]
    y = _info_card(c, facts_lines, x0+M, y, BODY_W, bg=OFF_WHITE)

    y = _divider(c, x0+M, y, BODY_W)

    # ── QR placeholder + disclaimer ───────────────────────────────────────────
    # QR code placeholder box
    qr_size = 28
    qr_x    = x0 + M
    qr_y    = y - qr_size
    c.setFillColor(WHITE)
    c.setStrokeColor(LIGHT_LINE)
    c.setLineWidth(0.5)
    c.rect(qr_x, qr_y, qr_size, qr_size, fill=1, stroke=1)
    c.setFont("Helvetica", 5)
    c.setFillColor(MUTED_TEXT)
    c.drawCentredString(qr_x + qr_size/2, qr_y + qr_size/2 - 3, "QR CODE")

    # Disclaimer beside QR
    disc = (
        "For healthcare professionals only. "
        "Refer to full prescribing information before clinical use. "
        "Data sourced from US FDA OpenFDA."
    )
    _wrap(c, disc, qr_x + qr_size + 6, y - 8,
          BODY_W - qr_size - 8,
          "Helvetica-Oblique", 6, 9, colour=MUTED_TEXT, max_lines=6)


def _spine_panel(c, data):
    x0 = P

    c.setFillColor(WHITE)
    c.rect(x0, 0, P, PAGE_H, fill=1, stroke=0)

    # Left teal stripe
    c.setFillColor(TEAL)
    c.rect(x0, 0, 5, PAGE_H, fill=1, stroke=0)

    # Right navy stripe
    c.setFillColor(NAVY)
    c.rect(x0 + P - 5, 0, 5, PAGE_H, fill=1, stroke=0)

    # ── Rotated drug name (vertical, centred) ─────────────────────────────────
    c.saveState()
    c.translate(x0 + P/2, PAGE_H/2)
    c.rotate(90)
    name = data.get("drug_name", "")
    c.setFont("Helvetica-Bold", 20)
    c.setFillColor(NAVY)
    tw = c.stringWidth(name, "Helvetica-Bold", 20)
    c.drawString(-tw/2, -7, name)
    c.restoreState()

    # Rotated generic name below drug name
    generic = data.get("generic_name","")
    if generic and generic.lower() != name.lower():
        c.saveState()
        c.translate(x0 + P/2 - 18, PAGE_H/2)
        c.rotate(90)
        c.setFont("Helvetica-Oblique", 9)
        c.setFillColor(TEAL)
        tw2 = c.stringWidth(generic, "Helvetica-Oblique", 9)
        c.drawString(-tw2/2, -4, generic)
        c.restoreState()

    # ── Decorative horizontal rule strips ─────────────────────────────────────
    for frac in [0.82, 0.18]:
        c.setFillColor(TEAL_LIGHT)
        c.rect(x0 + 10, PAGE_H*frac - 1, P - 20, 2, fill=1, stroke=0)

    # ── Amber dot accents ─────────────────────────────────────────────────────
    for frac in [0.87, 0.13]:
        c.setFillColor(AMBER)
        c.circle(x0 + P/2, PAGE_H*frac, 5, fill=1, stroke=0)

    # ── Mini drug fact pills (vertical spine content filler) ──────────────────
    mini_facts = [
        ("Route", "Oral"),
        ("Rx", "Only"),
        ("Form", "Tablet"),
    ]
    fact_y = PAGE_H * 0.72
    for lbl, val in mini_facts:
        # label pill
        pill_w = 48
        pill_x = x0 + P/2 - pill_w/2
        c.setFillColor(TEAL_LIGHT)
        c.roundRect(pill_x, fact_y - 5, pill_w, 14, 4, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 6.5)
        c.setFillColor(NAVY)
        c.drawString(pill_x + 4, fact_y, lbl)
        c.setFont("Helvetica", 6.5)
        c.setFillColor(TEAL)
        lw = c.stringWidth(lbl + " ", "Helvetica-Bold", 6.5)
        c.drawString(pill_x + 4 + lw + 2, fact_y, val)
        fact_y -= 20

    # ── Bottom class badge ────────────────────────────────────────────────────
    dc = data.get("drug_class","")
    if dc:
        fact_y_b = PAGE_H * 0.28
        _pill_badge(c, dc[:32], x0 + P/2, fact_y_b, bg=NAVY)


# ══════════════════════════════════════════════════════════════════════════════
#  PAGE 2 — Inside spread
#  [CLINICAL (x=0)] [OVERVIEW (x=P)] [SAFETY (x=2P)]
# ══════════════════════════════════════════════════════════════════════════════

def _inside_left(c, data):
    """Clinical Information — Indications, Contraindications, extra notes."""
    x0 = 0

    c.setFillColor(TEAL_LIGHT)
    c.rect(x0, 0, P, PAGE_H, fill=1, stroke=0)

    y = _panel_header(c, "Clinical Information", "", x0, P, bg=TEAL, h=13*mm)

    y = _section(c, "Indications & Usage",
                 data.get("indications","Not listed."),
                 x0+M, y, BODY_W, max_lines=9, bar_bg=TEAL)

    y = _section(c, "Contraindications",
                 data.get("contraindications","Not listed."),
                 x0+M, y, BODY_W, max_lines=7, bar_bg=NAVY)

    y = _divider(c, x0+M, y, BODY_W)

    # ── Clinical Use Notes (drug-specific) ───────────────────────────────────
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(NAVY)
    c.drawString(x0+M, y, "CLINICAL USE NOTES")
    y -= 14

    notes = data.get("clinical_notes", [
        "Monitor patient response at each clinical visit.",
        "Counsel patients on proper administration and adherence.",
        "Report any new or worsening symptoms promptly.",
    ])
    y = _dot_list(c, notes, x0+M, y, BODY_W, font_size=7.5, leading=11)

    y = _divider(c, x0+M, y, BODY_W)

    # ── Patient population (drug-specific) ───────────────────────────────────
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(NAVY)
    c.drawString(x0+M, y, "PATIENT POPULATION")
    y -= 14

    pop_lines = data.get("patient_pop", [
        ("Adults:",    "18 years and older"),
        ("Geriatric:", "Use with caution"),
        ("Pregnancy:", "Consult physician"),
    ])
    _info_card(c, pop_lines, x0+M, y, BODY_W, bg=WHITE)


def _inside_centre(c, data):
    """Drug Overview — Description, Mechanism, Dosage."""
    x0 = P

    c.setFillColor(WHITE)
    c.rect(x0, 0, P, PAGE_H, fill=1, stroke=0)

    # Left teal border rule
    c.setFillColor(TEAL)
    c.rect(x0, 0, 3, PAGE_H, fill=1, stroke=0)

    y = _panel_header(c, "Drug Overview", "", x0, P, bg=NAVY, h=13*mm)

    y = _section(c, "Description",
                 data.get("description","Not available."),
                 x0+M, y, BODY_W, max_lines=8, bar_bg=NAVY)

    y = _section(c, "Dosage & Administration",
                 data.get("dosage","Not available."),
                 x0+M, y, BODY_W, max_lines=9, bar_bg=TEAL)

    y = _divider(c, x0+M, y, BODY_W)

    # ── Dosage quick reference (drug-specific) ──────────────────────────────
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(NAVY)
    c.drawString(x0+M, y, "DOSAGE QUICK REFERENCE")
    y -= 14

    dose_lines = data.get("dosage_summary", [
        ("Dosing:", "Per prescribing information"),
        ("Route:", "Oral"),
        ("Administration:", "As directed by physician"),
    ])
    y = _info_card(c, dose_lines, x0+M, y, BODY_W, bg=GREY_BG)

    y = _divider(c, x0+M, y, BODY_W)

    # ── Mechanism of action (drug-specific) ──────────────────────────────────
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(NAVY)
    c.drawString(x0+M, y, "MECHANISM OF ACTION")
    y -= 14

    moa = data.get("moa", [
        "Modulates physiological pathways to achieve therapeutic effect.",
        "Refer to full prescribing information for detailed pharmacology.",
    ])
    _dot_list(c, moa, x0+M, y, BODY_W, font_size=7.5, leading=11)


def _inside_right(c, data):
    """Safety Information — Warnings, Adverse Reactions, Monitoring."""
    x0 = P * 2

    c.setFillColor(GREY_BG)
    c.rect(x0, 0, P, PAGE_H, fill=1, stroke=0)

    y = _panel_header(c, "Safety Information", "", x0, P, bg=NAVY, h=13*mm)

    # Warnings with amber bar
    y = _section_bar(c, "Warnings & Precautions",
                     x0+M, y, BODY_W, bg=AMBER, fg=DARK_TEXT)
    warn_top = y
    y = _wrap(c, data.get("warnings","Not listed."),
              x0+M+8, y, BODY_W-10,
              "Helvetica", 8, 11.5, colour=MID_TEXT, max_lines=8)
    # Amber left rule
    c.setFillColor(AMBER)
    c.rect(x0+M, y+2, 3, warn_top - y - 4, fill=1, stroke=0)
    y -= 6

    y = _section(c, "Adverse Reactions",
                 data.get("adverse_reactions","Not listed."),
                 x0+M, y, BODY_W, max_lines=6, bar_bg=NAVY)

    y = _divider(c, x0+M, y, BODY_W)

    # ── Monitoring parameters (drug-specific) ───────────────────────────────
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(NAVY)
    c.drawString(x0+M, y, "MONITORING PARAMETERS")
    y -= 14

    monitoring = data.get("monitoring", [
        "Vital signs — at each clinical visit",
        "Signs of adverse reactions — ongoing",
        "Therapeutic response — periodically",
    ])
    y = _dot_list(c, monitoring, x0+M, y, BODY_W, font_size=7.5, leading=11)

    y = _divider(c, x0+M, y, BODY_W)

    # ── Drug interactions (drug-specific) ────────────────────────────────────
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(NAVY)
    c.drawString(x0+M, y, "NOTABLE DRUG INTERACTIONS")
    y -= 14

    interactions = data.get("interactions", [
        ("Other medications:", "Check for interactions with prescriber"),
    ])
    _info_card(c, interactions, x0+M, y, BODY_W, bg=AMBER_LIGHT)


# ══════════════════════════════════════════════════════════════════════════════
#  Public API
# ══════════════════════════════════════════════════════════════════════════════

def generate_brochure(data: dict, output_path: str | None = None) -> bytes:
    buf = io.BytesIO()
    c   = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setTitle(f"{data.get('drug_name','Drug')} — Prescribing Brochure")
    c.setAuthor("MedicoMarketing Brochure Generator")

    # Page 1 — Outside
    _back_panel(c, data)
    _spine_panel(c, data)
    _front_cover(c, data)
    c.showPage()

    # Page 2 — Inside
    _inside_left(c, data)
    _inside_centre(c, data)
    _inside_right(c, data)
    c.showPage()

    c.save()
    pdf_bytes = buf.getvalue()

    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
        print(f"[brochure] Saved → {output_path}")

    return pdf_bytes


if __name__ == "__main__":
    from fetcher import fetch_drug_data
    data = fetch_drug_data("metformin")
    if "error" in data:
        print(data["error"])
    else:
        generate_brochure(data, "test_brochure.pdf")
        print("Done.")
