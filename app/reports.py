"""
Modulo de Generacion Automatica de Certificados Tributarios
(Ley N° 21.210 Art. 31 N° 3).

ReMarket 2.0 - Gestion de Rescate de Mermas e Inocuidad Alimentaria.
"""

import io
import uuid
from datetime import date

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


COLORS = {
    "heading": HexColor("#064E3B"),  # Verde bosque profundo ODS 12
    "accent": HexColor("#B8860B"),  # Amarillo dorado ODS 12
    "body": HexColor("#1F2937"),
    "bg_alt": HexColor("#F3F4F6"),
    "green_light": HexColor("#ECFDF5"),
    "white": HexColor("#FFFFFF"),
    "muted": HexColor("#4B5563"),
}

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        "CertTitle",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=COLORS["heading"],
        alignment=TA_CENTER,
        spaceAfter=4,
    )
)
styles.add(
    ParagraphStyle(
        "CertSub",
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=COLORS["accent"],
        alignment=TA_CENTER,
        spaceAfter=14,
    )
)
styles.add(
    ParagraphStyle(
        "H1_Custom",
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=COLORS["heading"],
        spaceBefore=10,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        "Body_Custom",
        fontName="Helvetica",
        fontSize=9,
        textColor=COLORS["body"],
        leading=13,
        alignment=TA_JUSTIFY,
    )
)
styles.add(
    ParagraphStyle(
        "TableHead",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=COLORS["white"],
        alignment=TA_CENTER,
    )
)
styles.add(
    ParagraphStyle(
        "TableBody",
        fontName="Helvetica",
        fontSize=8,
        textColor=COLORS["body"],
        leading=11,
    )
)
styles.add(
    ParagraphStyle(
        "TableBodyCenter",
        fontName="Helvetica",
        fontSize=8,
        textColor=COLORS["body"],
        leading=11,
        alignment=TA_CENTER,
    )
)
styles.add(
    ParagraphStyle(
        "StatNum",
        fontName="Helvetica-Bold",
        fontSize=13,
        textColor=COLORS["heading"],
        alignment=TA_CENTER,
    )
)
styles.add(
    ParagraphStyle(
        "StatLabel",
        fontName="Helvetica",
        fontSize=8,
        textColor=COLORS["muted"],
        alignment=TA_CENTER,
    )
)


def generar_pdf_certificado_bytes(
    donante: dict,
    beneficiario: dict,
    productos_entregados: list,
) -> bytes:
    """Genera un certificado de donacion tributaria en memoria."""
    buffer = io.BytesIO()
    margin = 0.75 * inch
    usable_w = 8.5 * inch - 2 * margin

    doc = BaseDocTemplate(
        buffer,
        pagesize=LETTER,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin + 10,
        bottomMargin=margin + 10,
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        usable_w,
        11 * inch - doc.topMargin - doc.bottomMargin,
        id="main",
    )
    doc.addPageTemplates([PageTemplate(id="cert_page", frames=frame)])

    story = []

    # Encabezado
    story.append(
        Paragraph(
            "CERTIFICADO DE DONACION DE EXCEDENTES",
            styles["CertTitle"],
        )
    )
    story.append(
        Paragraph(
            "RESPALDO DE GASTO TRIBUTARIO - ARTICULO 31 N° 3 LEY N° 21.210",
            styles["CertSub"],
        )
    )

    # Datos generales
    folio = f"RMK-{date.today().year}-{uuid.uuid4().hex[:6].upper()}"
    header_data = [
        [
            Paragraph(
                f"<b>Folio Certificado:</b> {folio}",
                styles["Body_Custom"],
            ),
            Paragraph(
                f"<b>Fecha Emision:</b> {date.today().strftime('%d/%m/%Y')}",
                styles["Body_Custom"],
            ),
        ],
        [
            Paragraph(
                f"<b>Empresa Donante:</b> {donante.get('nombre')}",
                styles["Body_Custom"],
            ),
            Paragraph(
                f"<b>RUT Donante:</b> {donante.get('rut', '76.452.180-K')}",
                styles["Body_Custom"],
            ),
        ],
        [
            Paragraph(
                f"<b>Organizacion Receptora:</b> {beneficiario.get('nombre')}",
                styles["Body_Custom"],
            ),
            Paragraph(
                f"<b>RUT Receptor SII:</b> "
                f"{beneficiario.get('rut', '65.129.400-2')}",
                styles["Body_Custom"],
            ),
        ],
        [
            Paragraph(
                "<b>Operador Logistico:</b> "
                "ReMarket 2.0 SpA (San Juan, Coquimbo)",
                styles["Body_Custom"],
            ),
            Paragraph(
                "<b>RUT Operador:</b> 77.892.310-5",
                styles["Body_Custom"],
            ),
        ],
    ]
    t_header = Table(
        header_data,
        colWidths=[usable_w * 0.55, usable_w * 0.45],
    )
    t_header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLORS["bg_alt"]),
                ("BOX", (0, 0), (-1, -1), 0.5, COLORS["accent"]),
                ("PADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(t_header)
    story.append(Spacer(1, 10))

    # Metricas del certificado
    total_kg = sum(p.get("kg", 0) for p in productos_entregados)
    valor_costo = total_kg * 4500
    impuesto_ahorrado = valor_costo * 0.40
    co2_evitado = total_kg * 1.5

    stat_cells = [
        [
            Paragraph(f"{total_kg:,.1f} kg", styles["StatNum"]),
            Paragraph(f"${valor_costo:,.0f} CLP", styles["StatNum"]),
            Paragraph(f"${impuesto_ahorrado:,.0f} CLP", styles["StatNum"]),
            Paragraph(f"{co2_evitado:,.1f} kg", styles["StatNum"]),
        ],
        [
            Paragraph("Total Rescatado", styles["StatLabel"]),
            Paragraph("Costo en Libros", styles["StatLabel"]),
            Paragraph("Impuesto 40% Evitado", styles["StatLabel"]),
            Paragraph("CO2 Evitado", styles["StatLabel"]),
        ],
    ]
    t_stats = Table(stat_cells, colWidths=[usable_w * 0.25] * 4)
    t_stats.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COLORS["green_light"]),
                ("BOX", (0, 0), (-1, -1), 0.5, COLORS["heading"]),
                ("LINEAFTER", (0, 0), (2, 1), 0.5, COLORS["heading"]),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t_stats)
    story.append(Spacer(1, 10))

    # Tabla de productos
    story.append(
        Paragraph(
            "1. Detalle de Lotes Retirados e Inspeccion de "
            "Inocuidad (DS 977/96)",
            styles["H1_Custom"],
        )
    )
    table_headers = [
        Paragraph(f"<b>{header}</b>", styles["TableHead"])
        for header in [
            "Producto",
            "Categoria",
            "Peso (kg)",
            "Vencimiento",
            "Inspeccion Inocuidad",
        ]
    ]
    rows = []
    for producto in productos_entregados:
        rows.append(
            [
                Paragraph(
                    producto.get("nombre", "Producto"),
                    styles["TableBody"],
                ),
                Paragraph(
                    producto.get("categoria", "Alimentos"),
                    styles["TableBody"],
                ),
                Paragraph(
                    f"{producto.get('kg', 0)} kg",
                    styles["TableBodyCenter"],
                ),
                Paragraph(
                    str(producto.get("vence", "N/A")),
                    styles["TableBodyCenter"],
                ),
                Paragraph(
                    "Aprobado (DS 977/96)",
                    styles["TableBodyCenter"],
                ),
            ]
        )

    t_prods = Table(
        [table_headers] + rows,
        colWidths=[
            usable_w * 0.30,
            usable_w * 0.22,
            usable_w * 0.14,
            usable_w * 0.14,
            usable_w * 0.20,
        ],
    )
    t_prods.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), COLORS["heading"]),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [COLORS["white"], COLORS["bg_alt"]],
                ),
                ("GRID", (0, 0), (-1, -1), 0.5, COLORS["muted"]),
                ("PADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t_prods)
    story.append(Spacer(1, 10))

    # Marco de certificacion legal
    decl_text = (
        "<b>RESPALDO DE GASTO TRIBUTARIO:</b> Se certifica que los bienes "
        "detallados han sido entregados a titulo gratuito a la "
        f"institucion <i>{beneficiario.get('nombre')}</i> registrada ante el "
        "SII. En conformidad con el Art. 31 N° 3 de la Ley N° 21.210, "
        f"este monto de <b>${valor_costo:,.0f} CLP</b> es deducible como "
        f"gasto necesario de la renta de "
        f"<i>{donante.get('nombre')}</i>, eximiendole del Impuesto Unico del "
        "40% por destruccion de inventarios."
    )
    story.append(Paragraph(decl_text, styles["Body_Custom"]))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
