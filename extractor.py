import polars as pl
import requests
import time

# ─────────────────────────────────────────────
# CONFIGURACIÓN INICIAL
# ─────────────────────────────────────────────

ARCHIVO_IDS    = "ids.csv"           # Archivo con los IDs a consultar
ARCHIVO_SALIDA = "RESULTADOS_FINAL.xlsx"  # Archivo donde se guardan los resultados

# La cookie se copia directamente del navegador (imagen 2 que compartiste)
# Caduca cada cierto tiempo — si el script se detiene con sesión expirada,
# deberás renovarla desde el navegador y pegarla aquí
COOKIE = 'JSESSIONID=539851AC69FA88D47D26E917D859531F; ...'

# Cabeceras HTTP que simulan ser un navegador Chrome normal
HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
    "Cookie":          COOKIE,
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "es-419,es;q=0.9,en;q=0.8",
    "Referer":         "http://200.188.126.15:8082/padron.bienestar/info/unico",
    "Connection":      "keep-alive"
}

BASE_URL = "http://200.188.126.15:8082/padron.bienestar/formato.rs"


# ─────────────────────────────────────────────
# FUNCIÓN PRINCIPAL DE CONSULTA
# ─────────────────────────────────────────────

def consultar_beneficiario(id_p):
    """
    Hace una petición GET al endpoint por cada ID.
    El servidor responde con un arreglo de valores separados por coma,
    por ejemplo: [valor0, valor1, ..., valor36, ...]
    Cada posición corresponde a un campo distinto del beneficiario.
    """
    try:
        r = requests.get(
            f"{BASE_URL}/getAtencionAM/{id_p}",
            headers=HEADERS,
            timeout=15  # Si el servidor no responde en 15s, se cancela
        )

        # Código 401 significa que la sesión expiró
        # Retornamos None para que el ciclo principal pueda detectarlo y parar
        if r.status_code == 401:
            return None

        # La respuesta llega como texto: "[valor0,valor1,valor2,...]"
        # .strip("[]") quita los corchetes
        # .split(",") separa por comas
        # .strip() elimina espacios en cada valor
        valores = [v.strip() for v in r.text.strip("[]").split(",")]

        # Función auxiliar para obtener un valor por posición de forma segura.
        # Si el índice no existe o es "null" / vacío, regresa "N/D"
        def get(i):
            v = valores[i] if len(valores) > i else "N/D"
            return "N/D" if v in ("null", "", None) else v

        # Retornamos un diccionario con los campos que nos interesan.
        # Los índices (28, 29, 30, 21, 36) corresponden a posiciones
        # en el arreglo de respuesta del servidor
        return {
            "ID_PADRON":       id_p,
            "COLONIA":         get(28),
            "CALLE":           get(29),
            "NUMERO_EXTERIOR": get(30),
            "TELEFONO":        get(21),
            "ESTATUS":         get(36),
        }

    # Si el servidor tarda demasiado, guardamos TIMEOUT para ese registro
    except requests.exceptions.Timeout:
        return {"ID_PADRON": id_p, "COLONIA": "TIMEOUT", "CALLE": "TIMEOUT",
                "NUMERO_EXTERIOR": "TIMEOUT", "TELEFONO": "TIMEOUT", "ESTATUS": "TIMEOUT"}

    # Cualquier otro error (red caída, respuesta malformada, etc.)
    except Exception as e:
        return {"ID_PADRON": id_p, "COLONIA": f"ERR:{e}", "CALLE": f"ERR:{e}",
                "NUMERO_EXTERIOR": f"ERR:{e}", "TELEFONO": f"ERR:{e}", "ESTATUS": f"ERR:{e}"}


# ─────────────────────────────────────────────
# PASO 1: CARGAR LOS IDs DESDE EL CSV
# ─────────────────────────────────────────────

print("📂 Cargando IDs...")

df_ids = pl.read_csv(ARCHIVO_IDS, infer_schema_length=0)
# infer_schema_length=0 → lee TODO como texto (string), evita errores de tipo

# FIX PRINCIPAL: en lugar de buscar la columna por nombre (que falla por el
# encoding de "ó" y "é"), tomamos directamente la primera columna con .columns[0]
ids = df_ids[df_ids.columns[0]].to_list()

total = len(ids)
print(f"✅ {total} IDs encontrados\n")


# ─────────────────────────────────────────────
# PASO 2: PROCESAR CADA ID UNO POR UNO
# ─────────────────────────────────────────────

resultados = []

for i, id_p in enumerate(ids):

    # Limpiamos el ID: convertimos "30563310.0" → "30563310"
    # Esto pasa cuando Polars lee números con decimales aunque sean enteros
    id_limpio = str(int(float(id_p)))

    # Llamamos al servidor
    res = consultar_beneficiario(id_limpio)

    # Si regresó None, la sesión expiró
    # Imprimimos en qué registro quedó para que puedas retomar desde ahí
    if res is None:
        print(f"\n⚠️  SESIÓN EXPIRADA en registro {i+1} (ID: {id_limpio})")
        print(f"   Renueva la COOKIE y cambia la línea de ids a:")
        print(f"   ids = ids[{i}:]")
        break

    resultados.append(res)

    # Imprimimos progreso en tiempo real para monitorear
    print(f"[{i+1:4d}/{total}] {id_limpio} | {res['COLONIA'][:30]} | {res['TELEFONO']}")

    # Pausa de 0.7 segundos entre peticiones para no saturar el servidor
    # y reducir el riesgo de que bloqueen la sesión
    time.sleep(0.7)


# ─────────────────────────────────────────────
# PASO 3: GUARDAR RESULTADOS EN EXCEL
# ─────────────────────────────────────────────

if resultados:
    df_final = pl.DataFrame(resultados)
    df_final.write_excel(ARCHIVO_SALIDA)
    print(f"\n✅ Guardado: {ARCHIVO_SALIDA}")
    print(f"   Procesados: {len(resultados)}/{total}")
