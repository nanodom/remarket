from app.reports import generar_pdf_certificado_bytes


def test_generar_pdf_certificado_devuelve_documento_pdf():
    pdf = generar_pdf_certificado_bytes(
        donante={"nombre": "Donante de prueba"},
        beneficiario={"nombre": "Beneficiario de prueba"},
        productos_entregados=[
            {
                "nombre": "Alimento de prueba",
                "categoria": "Alimentos",
                "kg": 2,
                "vence": "2026-12-31",
            }
        ],
    )

    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 100
