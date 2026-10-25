import os
import httpx

ABUSEIPDB_API_KEY = os.getenv("ABUSEIPDB_API_KEY", "")
ABUSEIPDB_URL = "https://api.abuseipdb.com/api/v2/check"

async def verificar_ip_abuseipdb(ip_address: str, max_age_in_days: int = 90) -> dict:
    """
    Consulta la reputación de una dirección IP en AbuseIPDB.
    Retorna un diccionario con el puntaje de abuso (abuseConfidenceScore), 
    si está en una lista negra, el país, etc.
    """
    if not ABUSEIPDB_API_KEY:
        # Si no hay API key configurada, puedes decidir si dejar pasar 
        # o lanzar una advertencia interna.
        return {"ipAddress": ip_address, "abuseConfidenceScore": 0, "whitelisted": False}

    headers = {
        "Key": ABUSEIPDB_API_KEY,
        "Accept": "application/json"
    }
    params = {
        "ipAddress": ip_address,
        "maxAgeInDays": max_age_in_days,
        "verbose": True
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(ABUSEIPDB_URL, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json().get("data", {})
                return {
                    "ipAddress": data.get("ipAddress"),
                    "isPublic": data.get("isPublic"),
                    "abuseConfidenceScore": data.get("abuseConfidenceScore", 0),
                    "countryCode": data.get("countryCode"),
                    "totalReports": data.get("totalReports", 0)
                }
            else:
                # Manejo de error de la API (ej. cuota excedida, key inválida)
                return {"error": f"Error en AbuseIPDB: {response.status_code}"}
        except httpx.RequestError:
            # Fallo de red o timeout
            return {"error": "No se pudo conectar con AbuseIPDB"}