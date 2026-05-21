from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    Image as RLImage,
)
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

BLUE = colors.HexColor("#1a3a6b")
BLUE_MID = colors.HexColor("#3a5a8a")
GRAY = colors.HexColor("#f5f5f5")
GRAY_TEXT = colors.HexColor("#777777")
DARK = colors.HexColor("#222222")
FONT_BOLD = "Helvetica-Bold"
FONT = "Helvetica"
MARGIN_LEFT = 40
MARGIN_RIGHT = 40
PAGE_W, PAGE_H = letter
USABLE_W = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT


def _cb(text, checked):
    return f"\u2611 {text}" if checked else "\u2610 " + text


def _yesno(val):
    s = str(val).strip().lower()
    return s in ("si", "s\u00ed", "yes", "s")


def _value(data, key, fallback="\u2014"):
    v = data.get(key, "")
    return str(v) if v else fallback


def _section_bar(number, title, usable_w):
    t = Table(
        [[Paragraph(f"{number}. {title}", ParagraphStyle("sb", fontName=FONT_BOLD, fontSize=10, leading=12, textColor=colors.white))]],
        colWidths=[usable_w],
    )
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return t


def _style(name, **kw):
    kw.setdefault("fontSize", 8)
    kw.setdefault("leading", 10)
    kw.setdefault("textColor", DARK)
    kw.setdefault("fontName", FONT)
    return ParagraphStyle(name, **kw)


def draw_header(data, now, usable_w):
    """Return header flowable."""
    items = []
    items.append(Spacer(1, 2))
    cw = [usable_w * 0.65, usable_w * 0.35]

    def _c(text, **kw):
        return Paragraph(text, _style("hc", **kw))

    s = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, -1), BLUE),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, 0), 10),
            ("RIGHTPADDING", (0, 0), (-1, 0), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
    )

    # Row 0: main title (full width)
    header0 = Table(
        [
            [
                _c("EXPEDIENTE M\u00c9DICO DIGITAL", fontSize=16, leading=18, fontName=FONT_BOLD),
                _c(f"Formulario N\u00b0 {data.get('encounter_id', '---')}", fontSize=8, leading=9, alignment=TA_RIGHT),
            ]
        ],
        colWidths=cw,
    )
    header0.setStyle(s)
    items.append(header0)

    # Row 1: subtitle + date
    header1 = Table(
        [[_c("EVALUACI\u00d3N PARA LICENCIA DE CONDUCIR \u00b7 COSTA RICA", fontSize=9, leading=11), _c(now.strftime("%d/%m/%Y"), fontSize=8, leading=9, alignment=TA_RIGHT)]],
        colWidths=cw,
    )
    header1.setStyle(s)
    items.append(header1)

    # Row 2: solicitante
    header2 = Table(
        [[_c(f"Solicitante: {_value(data, 'full_name', '---')}", fontSize=9, leading=11), _c("", fontSize=8)]],
        colWidths=cw,
    )
    header2.setStyle(s)
    items.append(header2)

    return items


def draw_id_images(front_path, back_path, usable_w):
    """Return ID images flowables."""
    items = []
    items.append(Spacer(1, 6))
    front_label = Paragraph(
        "C\u00c9DULA \u2013 FRENTE",
        _style("fl", fontSize=7, alignment=TA_CENTER, textColor=BLUE, fontName=FONT_BOLD),
    )
    back_label = Paragraph(
        "C\u00c9DULA \u2013 REVERSO",
        _style("bl", fontSize=7, alignment=TA_CENTER, textColor=BLUE, fontName=FONT_BOLD),
    )
    img_w = 200
    img_h = 130
    has_front = front_path and front_path.exists()
    has_back = back_path and back_path.exists()
    if has_front and has_back:
        try:
            fi = RLImage(str(front_path), width=img_w, height=img_h, kind="proportional")
            bi = RLImage(str(back_path), width=img_w, height=img_h, kind="proportional")
            id_table = Table(
                [[front_label, back_label], [fi, bi]],
                colWidths=[img_w + 20, img_w + 20],
            )
            id_table.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("BOX", (0, 0), (0, 0), 0.5, BLUE),
                        ("BOX", (1, 0), (1, 0), 0.5, BLUE),
                        ("BOX", (0, 1), (0, 1), 0.5, BLUE),
                        ("BOX", (1, 1), (1, 1), 0.5, BLUE),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            items.append(id_table)
        except Exception as e:
            items.append(Paragraph(f"(Imagen no disponible: {e})", _style("err", fontSize=7, textColor=GRAY_TEXT)))
    elif has_front:
        items.append(front_label)
        items.append(RLImage(str(front_path), width=img_w, height=img_h, kind="proportional"))
    elif has_back:
        items.append(back_label)
        items.append(RLImage(str(back_path), width=img_w, height=img_h, kind="proportional"))
    items.append(Spacer(1, 8))
    return items


def draw_general_data(data, usable_w):
    """Return Datos Generales section flowables."""
    items = []
    items.append(_section_bar(1, "DATOS GENERALES", usable_w))
    items.append(Spacer(1, 4))

    raw_id = data.get("identification", "")
    raw_id_type = data.get("id_type", "")
    id_display = f"{raw_id} ({raw_id_type})" if raw_id_type else raw_id

    address_parts = []
    for k in ("province", "canton", "district_or_locality", "exact_address"):
        v = data.get(k, "")
        if v and str(v).strip():
            address_parts.append(str(v).strip())
    address = ", ".join(address_parts) if address_parts else "\u2014"

    organ_raw = data.get("organ_donor", "")
    organ = str(organ_raw) if organ_raw else "\u2014"

    left_col = [
        ["C\u00e9dula / DIMEX", id_display],
        ["Correo electr\u00f3nico", _value(data, "email")],
        ["Ocupaci\u00f3n", _value(data, "profession")],
        ["N\u00famero telef\u00f3nico", _value(data, "whatsapp")],
    ]
    right_col = [
        ["Direcci\u00f3n", address],
        ["Estado civil", _value(data, "civil_status")],
        ["Donador de \u00f3rganos", organ],
    ]
    max_rows = max(len(left_col), len(right_col))
    while len(left_col) < max_rows:
        left_col.append(["", ""])
    while len(right_col) < max_rows:
        right_col.append(["", ""])

    cw = usable_w * 0.48
    body = []
    for i in range(max_rows):
        body.append(
            [
                Paragraph(f"<b>{left_col[i][0]}:</b>", _style("fl", fontSize=7.5, textColor=BLUE_MID)),
                Paragraph(str(left_col[i][1]), _style("fv", fontSize=7.5)),
                Paragraph(f"<b>{right_col[i][0]}:</b>", _style("fl", fontSize=7.5, textColor=BLUE_MID)),
                Paragraph(str(right_col[i][1]), _style("fv", fontSize=7.5)),
            ]
        )
    t = Table(body, colWidths=[cw * 0.4, cw * 0.6, cw * 0.4, cw * 0.6])
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e0e0e0")),
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, GRAY]),
            ]
        )
    )
    items.append(t)
    items.append(Spacer(1, 8))
    return items


def draw_medical_data(data, usable_w):
    """Return Datos Medicos section flowables."""
    items = []
    items.append(_section_bar(2, "DATOS M\u00c9DICOS", usable_w))
    items.append(Spacer(1, 4))

    def v(key):
        return data.get(key, "")

    # 2.1 Enfermedades
    has_ill = _yesno(v("has_illness"))
    ill_parts = [f"<b>Enfermedades:</b> {_cb('S\u00ed', has_ill)}  {_cb('No', not has_ill)}"]
    if has_ill:
        ill_val = v("illnesses")
        if ill_val:
            ill_parts.append(f"<b>Cu\u00e1les:</b> {ill_val}")
        tx = v("treatments")
        if tx:
            ill_parts.append(f"<b>Medicamentos/Tratamientos:</b> {tx}")

    # 2.2 Fuma
    smk = _yesno(v("smokes"))
    smk_parts = [f"<b>Fuma:</b> {_cb('S\u00ed', smk)}  {_cb('No', not smk)}"]
    if smk:
        sf = v("smoke_frequency")
        if sf:
            smk_parts.append(f"<b>Veces/semana:</b> {sf}")
        sp = v("smoke_product")
        if sp:
            smk_parts.append(f"<b>Tipo:</b> {sp}")

    # 2.3 Toma licor
    drk = _yesno(v("drinks"))
    drk_parts = [f"<b>Toma licor:</b> {_cb('S\u00ed', drk)}  {_cb('No', not drk)}"]
    if drk:
        df = v("drink_frequency")
        if df:
            drk_parts.append(f"<b>Cu\u00e1nto:</b> {df}")

    # 2.4 Drogas
    drg = _yesno(v("uses_drugs"))
    drg_parts = [f"<b>Drogas:</b> {_cb('S\u00ed', drg)}  {_cb('No', not drg)}"]
    if drg:
        dt = v("drug_type")
        if dt:
            drg_parts.append(f"<b>Tipo:</b> {dt}")
        df2 = v("drug_frequency")
        if df2:
            drg_parts.append(f"<b>Frecuencia:</b> {df2}")

    # 2.5 Peso
    wgt = v("weight")
    wgt_str = f"{wgt} kg" if wgt else "\u2014"

    # 2.6 Estatura
    hgt = v("height")
    hgt_str = f"{hgt} cm" if hgt else "\u2014"

    # 2.7 Lentes
    gls = _yesno(v("uses_glasses"))
    gls_parts = [f"<b>Usa lentes:</b> {_cb('S\u00ed', gls)}  {_cb('No', not gls)}"]
    if gls:
        gu = v("glasses_use")
        if gu:
            gls_parts.append(f"<b>Uso:</b> {gu}")

    # 2.8 Lateralidad
    lat = v("laterality")
    lat_str = lat if lat else "\u2014"

    # 2.9 Tipo de licencia
    lic_raw = v("license_types")
    if isinstance(lic_raw, str):
        lic_list = [x.strip().upper() for x in lic_raw.replace(",", " ").split() if x.strip()]
    elif isinstance(lic_raw, (list, tuple)):
        lic_list = [str(x).strip().upper() for x in lic_raw if str(x).strip()]
    else:
        lic_list = []
    lic_cells = "  ".join(_cb(license_type, license_type in lic_list) for license_type in ["A", "B", "C", "D", "E"])

    med_left = [
        Paragraph(" ".join(ill_parts), _style("med", fontSize=7.5, leading=11)),
        Paragraph(" ".join(smk_parts), _style("med", fontSize=7.5, leading=11)),
        Paragraph(" ".join(drk_parts), _style("med", fontSize=7.5, leading=11)),
        Paragraph(" ".join(drg_parts), _style("med", fontSize=7.5, leading=11)),
        Paragraph(f"<b>Peso:</b> {wgt_str}", _style("med", fontSize=7.5, leading=11)),
        Paragraph(f"<b>Estatura:</b> {hgt_str}", _style("med", fontSize=7.5, leading=11)),
    ]
    med_right = [
        Paragraph(" ".join(gls_parts), _style("med", fontSize=7.5, leading=11)),
        Paragraph(f"<b>Lateralidad:</b> {lat_str}", _style("med", fontSize=7.5, leading=11)),
        Paragraph(f"<b>Tipos de licencia:</b><br/>{lic_cells}", _style("med", fontSize=7.5, leading=11)),
    ]

    max_mr = max(len(med_left), len(med_right))
    while len(med_left) < max_mr:
        med_left.append(Paragraph("", _style("_", fontSize=6)))
    while len(med_right) < max_mr:
        med_right.append(Paragraph("", _style("_", fontSize=6)))

    body = [[med_left[i], med_right[i]] for i in range(max_mr)]
    mw = usable_w * 0.48
    mt = Table(body, colWidths=[mw, mw])
    mt.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#e0e0e0")),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, GRAY]),
            ]
        )
    )
    items.append(mt)
    items.append(Spacer(1, 4))

    truth_raw = v("truth_declaration")
    truth_display = "Aceptada por el paciente" if str(truth_raw).strip().lower() == "accepted" else (str(truth_raw) if truth_raw else "\u2014")
    items.append(
        Paragraph(
            f"<b>Declaraci\u00f3n de veracidad:</b> {truth_display}",
            _style("td", fontSize=7, textColor=BLUE_MID, fontName=FONT_BOLD),
        )
    )
    items.append(Spacer(1, 4))
    return items


def draw_observations(usable_w):
    """Return Observaciones section flowables."""
    items = []
    items.append(_section_bar(3, "OBSERVACIONES DEL M\u00c9DICO EVALUADOR", usable_w))
    items.append(Spacer(1, 4))
    lines = [[Paragraph("_" * 90, _style("ol", fontSize=6, textColor=GRAY_TEXT, leading=8))] for _ in range(5)]
    ot = Table(lines, colWidths=[usable_w])
    ot.setStyle(
        TableStyle(
            [
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    items.append(ot)
    items.append(
        Paragraph(
            "Hallazgos, recomendaciones y observaciones del m\u00e9dico evaluador.",
            _style("oh", fontSize=6.5, textColor=GRAY_TEXT, leading=8),
        )
    )
    items.append(Spacer(1, 10))
    return items


def draw_signatures(usable_w):
    """Return signatures flowables."""
    sig_w = usable_w * 0.45
    t = Table(
        [
            [
                Paragraph(
                    "____________________________<br/><b>SOLICITANTE</b><br/>Firma y c\u00e9dula",
                    _style("sig", fontSize=8, alignment=TA_CENTER, leading=12),
                ),
                Paragraph("", _style("_")),
                Paragraph(
                    "____________________________<br/><b>M\u00c9DICO EVALUADOR</b><br/>Nombre, firma y c\u00f3digo",
                    _style("sig", fontSize=8, alignment=TA_CENTER, leading=12),
                ),
            ]
        ],
        colWidths=[sig_w, usable_w * 0.1, sig_w],
    )
    t.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return [t, Spacer(1, 8)]


def draw_footer(now):
    """Return footer + legal disclaimer flowables."""
    disclaimer = (
        "La informaci\u00f3n contenida en este documento corresponde exclusivamente a los datos "
        "proporcionados por el paciente mediante formulario. El paciente declara que los datos "
        "suministrados son reales, correctos y completos. Adem\u00e1s, dicha informaci\u00f3n ser\u00e1 "
        "revisada, verificada y valorada por el m\u00e9dico antes de emitir cualquier criterio cl\u00ednico, "
        "diagn\u00f3stico o decisi\u00f3n m\u00e9dica."
    )
    return [
        Paragraph(disclaimer, _style("disc", fontSize=6, leading=7, textColor=GRAY_TEXT)),
        Spacer(1, 4),
        Paragraph(
            f"Documento generado el {now.strftime('%d/%m/%Y')} | Expediente M\u00e9dico Digital | Respaldo para evaluaci\u00f3n m\u00e9dica de licencia de conducir",
            _style("footer", fontSize=6, leading=7, textColor=GRAY_TEXT, alignment=TA_CENTER, fontName=FONT),
        ),
    ]


def _resolve_for_pdf(path_val):
    """Resolve storage key or Path to a real filesystem Path."""
    if isinstance(path_val, Path):
        return path_val
    p = Path(path_val)
    if p.is_absolute():
        return p
    from app.storage import storage

    try:
        return storage.resolve(path_val)
    except Exception:
        return p


def build_pdf(pdf_path, data, front_path, back_path, source="remote"):
    now = datetime.now()
    resolved_pdf = _resolve_for_pdf(pdf_path)
    resolved_front = _resolve_for_pdf(front_path)
    resolved_back = _resolve_for_pdf(back_path)

    story = []
    story.extend(draw_header(data, now, USABLE_W))
    story.extend(draw_id_images(resolved_front, resolved_back, USABLE_W))
    story.extend(draw_general_data(data, USABLE_W))
    story.extend(draw_medical_data(data, USABLE_W))

    origin_text = "Origen del formulario: Atenci\u00f3n presencial" if source == "in_person" else "Origen del formulario: Enlace enviado al paciente"
    story.append(Paragraph(origin_text, _style("or", fontSize=6.5, textColor=GRAY_TEXT)))

    story.extend(draw_observations(USABLE_W))
    story.extend(draw_signatures(USABLE_W))
    story.extend(draw_footer(now))

    doc = SimpleDocTemplate(
        str(resolved_pdf),
        pagesize=letter,
        rightMargin=MARGIN_RIGHT,
        leftMargin=MARGIN_LEFT,
        topMargin=24,
        bottomMargin=24,
    )
    doc.build(story)
