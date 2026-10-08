from pathlib import Path
import base64
import io
import json
import requests
import rawpy
from PIL import Image


# ============================================================
# PHOTOIA - ANALISIS FOTOGRAFICO
# ============================================================

IMAGE_PATH = Path("_DSC2125.NEF")
MODEL = "llava:13b"

OLLAMA_URL = "http://localhost:11434/api/generate"

MAX_IMAGE_SIZE = 1024
TIMEOUT = 900

ANALYSIS_FILE = Path("llava_analysis.txt")


# ============================================================
# 1. INICIO
# ============================================================

print("=" * 60)
print("PHOTOIA")
print("=" * 60)

print(f"Fotografía: {IMAGE_PATH}")
print(f"Modelo: {MODEL}")
print()


# ============================================================
# 2. COMPROBAR ARCHIVO
# ============================================================

if not IMAGE_PATH.exists():

    print("ERROR: No se encontró el archivo:")
    print(IMAGE_PATH.resolve())

    raise SystemExit(1)


# ============================================================
# 3. PROCESAR RAW
# ============================================================

print("Procesando RAW...")

try:

    with rawpy.imread(str(IMAGE_PATH)) as raw:

        rgb = raw.postprocess(
            use_camera_wb=True,
            half_size=True,
            output_bps=8,
            no_auto_bright=False
        )

except Exception as e:

    print()
    print("ERROR procesando el archivo RAW:")
    print(e)

    raise SystemExit(1)


print(f"RAW procesado: {rgb.shape}")


# ============================================================
# 4. CONVERTIR A PIL
# ============================================================

try:

    image = Image.fromarray(rgb)

except Exception as e:

    print()
    print("ERROR convirtiendo la imagen:")
    print(e)

    raise SystemExit(1)


width, height = image.size


# ============================================================
# 5. REDUCIR TAMAÑO PARA OLLAMA
# ============================================================

scale = min(
    1.0,
    MAX_IMAGE_SIZE / max(width, height)
)


if scale < 1.0:

    new_size = (
        int(width * scale),
        int(height * scale)
    )

    image = image.resize(
        new_size,
        Image.Resampling.LANCZOS
    )


print(f"Imagen enviada a Ollama: {image.size}")


# ============================================================
# 6. JPEG TEMPORAL EN MEMORIA
# ============================================================
#
# IMPORTANTE:
# No se crea ningún archivo JPG en el disco.
#
# El JPEG solamente existe temporalmente en memoria
# para enviarlo al modelo de visión.
#

buffer = io.BytesIO()

try:

    image.save(
        buffer,
        format="JPEG",
        quality=85
    )

except Exception as e:

    print()
    print("ERROR creando imagen temporal:")
    print(e)

    raise SystemExit(1)


image_base64 = base64.b64encode(
    buffer.getvalue()
).decode("utf-8")


buffer.close()


# ============================================================
# 7. PROMPT DE ANALISIS
# ============================================================

prompt = """
Actúa como un fotógrafo profesional y editor fotográfico experto.

Analiza cuidadosamente la fotografía que recibiste.

NO inventes información que no puedas observar.

NO intentes adivinar:

- cámara
- lente
- ISO
- velocidad
- apertura
- distancia focal
- ubicación
- condiciones de iluminación que no sean visibles

Quiero una evaluación VISUAL REAL de la fotografía.

Analiza específicamente:

1. EXPOSICIÓN

Determina si la fotografía parece:

- subexpuesta
- correctamente expuesta
- sobreexpuesta

Observa especialmente:

- zonas demasiado brillantes
- zonas demasiado oscuras
- pérdida visible de detalle
- distribución general de luminosidad

2. BALANCE DE BLANCOS

Observa si existe alguna dominante de color.

Determina si la imagen parece:

- demasiado cálida
- demasiado fría
- demasiado verde
- demasiado magenta
- razonablemente neutra

Si el balance de blancos parece correcto, dilo.

3. CONTRASTE Y TONALIDAD

Evalúa:

- contraste general
- negros
- blancos
- sombras
- altas luces

Indica qué debería modificarse.

4. COLOR

Evalúa:

- saturación
- vibrancia
- colores dominantes
- naturalidad de los colores

Indica si algún color parece excesivo o apagado.

5. NITIDEZ Y DETALLE

Evalúa lo que realmente puedas observar:

- nitidez
- detalle
- microcontraste
- textura
- posible falta de enfoque

No inventes problemas de enfoque.

6. RUIDO

Busca ruido visible.

Si no puedes observar ruido claramente, indica:

"No se observa ruido significativo."

No recomiendes reducción de ruido solamente porque la fotografía sea RAW.

7. COMPOSICIÓN

Evalúa:

- encuadre
- composición
- elementos que distraigan
- espacio innecesario
- posible necesidad de recorte
- posible inclinación del horizonte

8. CALIDAD GENERAL

Identifica los principales problemas visuales.

Después identifica las mejoras que tendrían mayor impacto.

NO hagas cambios innecesarios.

============================================================
AJUSTES RECOMENDADOS
============================================================

Después del análisis proporciona valores aproximados de CAMBIO.

Utiliza estos rangos:

Exposure:
-2.0 a +2.0 EV

Contrast:
-50 a +50

Highlights:
-100 a +100

Shadows:
-100 a +100

Whites:
-100 a +100

Blacks:
-100 a +100

Temperature:
-100 a +100

Tint:
-100 a +100

Vibrance:
-100 a +100

Saturation:
-100 a +100

Clarity:
-100 a +100

Texture:
-100 a +100

Sharpening:
-100 a +100

Noise reduction:
-100 a +100

Rotation:
-45 a +45 grados

IMPORTANTE:

Los valores representan CAMBIOS recomendados.

No representan valores absolutos de la fotografía.

Si un ajuste realmente no necesita modificación, utiliza 0.

No cambies todos los controles por obligación.

Prioriza solamente los ajustes que realmente mejorarían la fotografía.

Para cada ajuste explica brevemente por qué.

NO devuelvas JSON.

NO utilices Markdown.

NO escribas una respuesta genérica.

Quiero una evaluación fotográfica concreta y específica basada únicamente en lo que puedes observar.
"""


# ============================================================
# 8. PREPARAR PETICION
# ============================================================

payload = {

    "model": MODEL,

    "prompt": prompt,

    "images": [
        image_base64
    ],

    "stream": False,

    "options": {

        "num_ctx": 4096,

        "temperature": 0.2

    }
}


# ============================================================
# 9. ENVIAR A OLLAMA
# ============================================================

print()
print("Analizando fotografía con Ollama...")
print("Esto puede tardar un poco.")
print()


try:

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=TIMEOUT
    )

    response.raise_for_status()


except requests.exceptions.Timeout:

    print()
    print("=" * 60)
    print("ERROR")
    print("=" * 60)
    print()
    print("Ollama tardó más de 15 minutos en responder.")

    raise SystemExit(1)


except requests.exceptions.ConnectionError:

    print()
    print("=" * 60)
    print("ERROR")
    print("=" * 60)
    print()
    print("No se pudo conectar con Ollama.")
    print()
    print("Comprueba que Ollama esté ejecutándose.")

    raise SystemExit(1)


except requests.exceptions.RequestException as e:

    print()
    print("=" * 60)
    print("ERROR")
    print("=" * 60)
    print()
    print("Error comunicando con Ollama:")
    print(e)

    raise SystemExit(1)


# ============================================================
# 10. OBTENER RESPUESTA
# ============================================================

try:

    data = response.json()

except Exception as e:

    print()
    print("ERROR: Ollama no devolvió JSON válido.")
    print(e)

    print()
    print("Respuesta recibida:")
    print(response.text)

    raise SystemExit(1)


result = data.get("response", "").strip()


# ============================================================
# 11. COMPROBAR RESULTADO
# ============================================================

if not result:

    print()
    print("ERROR:")
    print("El modelo no devolvió ningún análisis.")

    print()
    print("Respuesta completa de Ollama:")
    print(json.dumps(data, indent=2, ensure_ascii=False))

    raise SystemExit(1)


# ============================================================
# 12. GUARDAR ANALISIS
# ============================================================

try:

    ANALYSIS_FILE.write_text(
        result,
        encoding="utf-8"
    )

except Exception as e:

    print()
    print("=" * 60)
    print("ERROR")
    print("=" * 60)
    print()
    print("No se pudo guardar el análisis.")
    print(e)

    raise SystemExit(1)


# ============================================================
# 13. MOSTRAR ANALISIS
# ============================================================

print()
print("=" * 60)
print("ANALISIS FOTOGRAFICO")
print("=" * 60)
print()

print(result)

print()
print("=" * 60)
print("ANALISIS GUARDADO")
print("=" * 60)
print()
print(f"Archivo: {ANALYSIS_FILE.resolve()}")


# ============================================================
# 14. FINAL
# ============================================================

print()
print("=" * 60)
print("PHOTOIA - ANALISIS TERMINADO")
print("=" * 60)