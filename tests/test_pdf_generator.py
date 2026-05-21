"""Test PDF generator meets all visual requirements."""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DOCTOR_PASSWORD", "test123")
os.environ.setdefault("SECRET_KEY", "test-secret-key")

from PIL import Image

from app.pdf_generator import build_pdf

DATA = {
    "encounter_id": "12345",
    "full_name": "Ronald Kane Fuertes Lucero",
    "identification": "1-1234-5678",
    "id_type": "cedula",
    "email": "ronald@test.com",
    "profession": "Ingeniero",
    "whatsapp": "8888-8888",
    "province": "San José",
    "canton": "Central",
    "district_or_locality": "Carmen",
    "exact_address": "200 m este",
    "organ_donor": "Sí",
    "civil_status": "Soltero(a)",
    "has_illness": "Sí",
    "illnesses": "Asma",
    "treatments": "Salbutamol",
    "smokes": "No",
    "drinks": "Sí",
    "drink_frequency": "Fines de semana",
    "uses_drugs": "No",
    "weight": "75",
    "height": "180",
    "uses_glasses": "No",
    "laterality": "Diestro(a)",
    "license_types": "B, C, E",
    "truth_declaration": "accepted",
}


def _fake_img(path):
    img = Image.new("RGB", (400, 250), color="blue")
    img.save(str(path))


def _decode_pdf_text(raw_text):
    """Decode PDF octal escape sequences (\\ddd) to unicode."""
    import re

    def _replace_octal(m):
        code = int(m.group(1), 8)
        return chr(code)

    return re.sub(r"\\(\d{3})", _replace_octal, raw_text)


def _extract_text(pdf_path):
    """Extract text from reportlab PDF (ASCII85 + zlib streams)."""
    import base64
    import re
    import zlib

    raw = pdf_path.read_bytes()
    text_parts = []

    objs = raw.split(b"endobj")
    for obj in objs:
        m = re.search(rb">>\s*stream\s+(.*?)\s*endstream", obj, re.DOTALL)
        if not m:
            continue
        data = m.group(1).strip()
        if data.startswith(b"Gb") or data.startswith(b"s4"):
            try:
                a85 = data
                if a85.endswith(b"~>"):
                    a85 = a85[:-2]
                data = base64.a85decode(a85)
            except Exception:  # noqa: S112
                continue
        try:
            data = zlib.decompress(data)
        except Exception:  # noqa: S112
            continue
        text = data.decode("latin-1")
        # Extract from Tj operators
        for tj in re.finditer(r"\(([^)]*)\)\s*Tj", text):
            chunk = tj.group(1)
            chunk = chunk.replace("\\(", "(").replace("\\)", ")")
            if len(chunk) > 2:
                text_parts.append(_decode_pdf_text(chunk))
        # Extract from TJ arrays: [(text) num (text)] TJ
        for tj in re.finditer(r"\[(.*?)\]\s*TJ", text):
            inner = tj.group(1)
            for m in re.finditer(r"\(([^)]*)\)", inner):
                chunk = m.group(1)
                chunk = chunk.replace("\\(", "(").replace("\\)", ")")
                if len(chunk) > 2:
                    text_parts.append(_decode_pdf_text(chunk))

    return "\n".join(text_parts)


def test_pdf_generation():
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "output.pdf"
        front = Path(d) / "f.jpg"
        back = Path(d) / "b.jpg"
        _fake_img(front)
        _fake_img(back)
        build_pdf(tmp, DATA, front, back, source="in_person")

        assert tmp.exists(), "PDF file was not created"
        assert tmp.stat().st_size > 5000, f"PDF too small: {tmp.stat().st_size}"

        text = _extract_text(tmp)

        # 1. Header core content
        assert "EXPEDIENTE" in text and "DIGITAL" in text, "Missing main header"
        assert "MEDICO" in text.replace("\u00c9", "E"), "Missing MEDICO in header"
        assert "Ronald Kane Fuertes Lucero" in text, "Missing patient name"

        # 2. ID photos
        assert "FRENTE" in text, "Missing front label"
        assert "REVERSO" in text, "Missing back label"

        # 3. Sections
        assert "1. DATOS GENERALES" in text, "Missing general data section"
        assert "DATOS MEDICOS" in text.replace("\u00c9", "E"), "Missing medical data section"
        assert "OBSERVACIONES DEL MEDICO EVALUADOR" in text.replace("\u00c9", "E").replace("\u00d3", "O"), "Missing observations section"

        # 4. Truth declaration
        assert "Aceptada por el paciente" in text, "accepted was not replaced"

        # 5. Units
        assert "kg" in text, "Missing kg for weight"
        assert "cm" in text, "Missing cm for height"

        # 6. Origin
        assert "presencial" in text, "Missing origin (presencial)"

        # 7. No "No indicado"
        assert "No indicado" not in text, '"No indicado" should not appear for unused fields'

        # 8. Signature area
        assert "SOLICITANTE" in text, "Missing solicitante signature"
        assert "MEDICO EVALUADOR" in text.replace("\u00c9", "E"), "Missing medico signature"

        # 9. Footer & disclaimer
        assert "Documento generado el" in text, "Missing footer date"
        low = text.lower().replace("\u00f3", "o").replace("\u00e1", "a").replace("\u00ed", "i").replace("\u00e9", "e").replace("\u00fa", "u")
        assert "informacion contenida en este documento" in low, "Missing legal disclaimer"

        # 10. Remote source variant
        tmp2 = Path(d) / "output_remote.pdf"
        build_pdf(tmp2, DATA, front, back, source="remote")
        text2 = _extract_text(tmp2)
        assert "Enlace enviado al paciente" in text2, "Missing remote origin text"
