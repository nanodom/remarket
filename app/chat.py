"""Asistente de ayuda de ReMarket con Google Gemini."""
import asyncio
import os
import unicodedata
from typing import Literal

from fastapi import APIRouter, Depends
from google import genai
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .models import Producto, SessionLocal

API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL = os.getenv("CHAT_MODEL", "gemini-3.8-flash")  # verifica que este nombre exista en tu cuenta

router = APIRouter()

client = None
if API_KEY:
  try:
    client = genai.Client(api_key=API_KEY)
    print("[i] Cliente de Gemini inicializado.")
  except Exception as e:
    print(f"[!] Error al inicializar cliente Gemini: {e}")
else:
  print("[i] GEMINI_API_KEY no definida: el asistente funcionará en modo básico.")


def get_db():
  with SessionLocal() as db:
    yield db


GUIA = """\
ReMarket 2.0 es una app para recuperar, clasificar y distribuir productos de primera necesidad.
Flujo: Registrar -> Clasificar -> Asignar -> Flota -> Rutas -> Seguimiento -> Indicadores.

Pestañas:
- Registrar: formulario de producto (nombre, categoría, kg, condición, vencimiento, donante). También permite agregar donantes o beneficiarios escribiendo su dirección (se geolocaliza sola). No se aceptan productos vencidos.
- Clasificar: tabla con puntaje y prioridad (solo lectura). Puntaje = peso de categoría (perecible 30, no perecible o higiene 20, abrigo 10) + urgencia por vencimiento (<=2 días: 15, <=7 días: 8) + estado (próximo a vencer +10, regular -3). Alta >=35, Media >=20, Baja el resto.
- Asignar: botón "Asignar automáticamente". Por orden de prioridad, elige el beneficiario más cercano al donante que necesite la categoría, tenga capacidad libre y, si es perecible, cadena de frío. Si no hay compatible, queda "Disponible" y se informa cuántos quedaron sin destino.
- Flota: CRUD de vehículos (capacidad en kg, cadena de frío, costo por km, costo fijo, turno, activo). Solo roles de gestión pueden modificarla. Un vehículo con productos En ruta no se puede desactivar ni eliminar.
- Rutas: botón "Planificar rutas". Reparte los productos Asignados entre los vehículos activos respetando capacidad, cadena de frío (los perecibles solo van en vehículos con frío) y duración del turno; cada vehículo sale de la base, hace sus retiros, sus entregas y vuelve. Usa OSRM para distancias reales. Los envíos que no caben quedan "Asignado" y se informa el motivo. Muestra km, jornada, costo, costo por retiro y ahorro vs. un viaje por envío.
- Seguimiento: estados Disponible -> Asignado -> En ruta -> Entregado. El botón "Marcar entregado" aparece solo en productos En ruta.
- Indicadores: km recorridos, costo por retiro, tiempo de entrega, kg recuperados y beneficiarios. Costo = km x costo por km del vehículo + costo fijo del vehículo + retiros x costo fijo por retiro.
"""

REGLAS = [
    (("registr", "agregar producto", "nuevo producto", "donar", "cargar producto"),
     "Ve al módulo de **Registrar**, completa el formulario y pulsa *Registrar producto*."),
    (("prioridad", "puntaje", "clasific"),
     "En **Clasificar** el puntaje suma el peso de la categoría (perecible 30, no perecible o higiene 20,"
     " abrigo 10), la urgencia por vencimiento y la condición. **Alta** desde 35, **Media** desde 20."),
    (("sin destino", "sin destinatario", "no se asigno", "no asign"),
     "Un producto queda sin destino si ningún beneficiario necesita su categoría, tiene capacidad libre"
     " o, en perecibles, cuenta con cadena de frío."),
    (("flota", "vehiculo", "camion"),
     "En **Flota** puedes agregar, editar o eliminar vehículos (capacidad, frío, costos y turno)."
     " Solo los roles de gestión pueden modificarla."),
    (("ruta", "planific"),
     "En **Rutas** pulsa *Planificar rutas*: el sistema reparte los productos Asignados entre los"
     " vehículos activos según capacidad, frío y turno."),
    (("hola", "ayuda", "como funciona", "que puedo", "empez", "buenas"),
     "¡Hola! Te guío por ReMarket. Pregúntame sobre el registro, clasificación, asignación, flota o rutas."),
]


def _norm(t: str) -> str:
  t = unicodedata.normalize("NFD", t.lower())
  return "".join(c for c in t if unicodedata.category(c) != "Mn")


def respuesta_basica(texto: str) -> str:
  t = _norm(texto)
  for claves, resp in REGLAS:
    if any(k in t for k in claves):
      return resp
  return (
      "No estoy seguro. Puedo ayudarte con el registro, clasificación,"
      " asignación, flota, rutas, seguimiento e indicadores."
  )


def contexto(db) -> str:
  por_estado = dict(db.execute(select(Producto.status, func.count()).group_by(Producto.status)).all())
  return f"Productos por estado: {por_estado or 'ninguno'}."


class Msg(BaseModel):
  role: Literal["user", "assistant"]
  content: str = Field(max_length=1500)


class ChatIn(BaseModel):
  mensajes: list[Msg] = Field(min_length=1, max_length=30)
  pestana: str = Field(default="", max_length=40)


async def _gemini(msgs: list[Msg], pestana: str, ctx: str) -> str:
  system_instruction = (
      "Eres el asistente de ayuda de la aplicación ReMarket 2.0. Respondes"
      " siempre en español, en tono cercano, breve (máximo 4-5 frases) y solo"
      " sobre cómo usar la app.\n\nGUÍA DE LA"
      f" APP:\n{GUIA}\nESTADO ACTUAL: {ctx}\nPestaña abierta:"
      f" {pestana or 'desconocida'}."
  )
  contents = [{"role": "user" if m.role == "user" else "model", "parts": [{"text": m.content}]}
              for m in msgs[-10:]]
  response = await asyncio.to_thread(
      client.models.generate_content,
      model=MODEL,
      contents=contents,
      config={"system_instruction": system_instruction, "max_output_tokens": 600},
  )
  return (response.text or "").strip()


@router.post("/api/chat")
async def chat(d: ChatIn, db=Depends(get_db)):
  ultimo = next((m.content for m in reversed(d.mensajes) if m.role == "user"), "")
  if client:
    try:
      txt = await _gemini(d.mensajes, d.pestana, contexto(db))
      if txt:
        return {"respuesta": txt, "modo": "ia"}
    except Exception as e:
      print(f"[!] Error de Gemini: {e}")
  return {"respuesta": respuesta_basica(ultimo), "modo": "basico"}