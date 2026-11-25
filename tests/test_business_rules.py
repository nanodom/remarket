from datetime import date, timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.logic import score
from app.main import ProductoIn, crear_producto
from app.models import Producto


def test_producto_vencido_o_que_vence_hoy_se_rechaza():
    for vence in (date.today() - timedelta(days=1), date.today()):
        producto = ProductoIn(
            nombre="Producto vencido",
            categoria="Alimentos perecibles",
            kg=2,
            estado="Bueno",
            vence=vence,
            donante_id=uuid4(),
        )

        with pytest.raises(HTTPException) as error:
            crear_producto(producto, db=None)

        assert error.value.status_code == 422
        assert error.value.detail == "Producto vencido: no apto para distribución"


def test_score_suma_categoria_urgencia_y_estado():
    producto = Producto(
        nombre="Leche",
        categoria="Alimentos perecibles",
        estado="Próximo a vencer",
        vence=date.today() + timedelta(days=2),
    )

    assert score(producto) == 55
