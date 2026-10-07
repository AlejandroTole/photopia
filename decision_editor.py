import json
import requests
from pathlib import Path


# ============================================================
# PHOTOIA - DECISION EDITOR
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

ANALYSIS_FILE = BASE_DIR / "image_analysis.json"
LLAVA_FILE = BASE_DIR / "llava_analysis.txt"
DECISION_FILE = BASE_DIR / "photo_decision.json"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL = "qwen2.5:7b"


# ============================================================
# UTILIDADES
# ============================================================

def first_value(data, keys, default=None):
    """
    Devuelve el primer valor existente y no None
    de una lista de posibles claves.
    """
    if not isinstance(data, dict):
        return default

    for key in keys:
        if key in data and data[key] is not None:
            return data[key]

    return default


def safe_float(value, default=0.0):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def clamp(value, minimum, maximum):
    value = safe_float(value, 0.0)
    return max(minimum, min(maximum, value))


# ============================================================
# CARGAR ANÁLISIS
# ============================================================

print("=" * 60)
print("PHOTOIA - DECISION EDITOR")
print("=" * 60)

print("\nCargando análisis objetivo...")

if not ANALYSIS_FILE.exists():
    raise FileNotFoundError(
        f"No existe el archivo: {ANALYSIS_FILE}"
    )

with open(ANALYSIS_FILE, "r", encoding="utf-8") as f:
    analysis = json.load(f)

print("OK: image_analysis.json")


print("\nCargando análisis visual de LLaVA...")

if not LLAVA_FILE.exists():
    raise FileNotFoundError(
        f"No existe el archivo: {LLAVA_FILE}"
    )

with open(LLAVA_FILE, "r", encoding="utf-8") as f:
    llava_analysis = f.read().strip()

print("OK: llava_analysis.txt")


# ============================================================
# SECCIONES DEL ANÁLISIS
# ============================================================

raw_sensor = analysis.get("raw_sensor", {})
rgb_rendered = analysis.get("rgb_rendered", {})

raw_statistics = raw_sensor.get("statistics", {})
raw_clipping = raw_sensor.get("clipping", {})

rgb_luminance = rgb_rendered.get("luminance", {})
rgb_clipping = rgb_rendered.get("clipping", {})
rgb_channels = rgb_rendered.get("channels", {})

raw_spatial = raw_sensor.get("spatial_analysis", {})
raw_spatial_summary = raw_spatial.get("summary", {})

rgb_spatial = rgb_rendered.get("spatial_analysis", {})
rgb_spatial_summary = rgb_spatial.get("summary", {})

spatial_color = rgb_rendered.get("spatial_color_analysis", {})
spatial_color_summary = spatial_color.get("summary", {})


# ============================================================
# CLIPPING
#
# image_analysis.json utiliza:
#
#   shadow_percent
#   highlight_percent
#
# ============================================================

raw_shadow_clipping = first_value(
    raw_clipping,
    [
        "shadow_percent",
        "shadow_clipping_percent",
        "shadow_clipping",
    ],
    default=0.0
)

raw_highlight_clipping = first_value(
    raw_clipping,
    [
        "highlight_percent",
        "highlight_clipping_percent",
        "highlight_clipping",
    ],
    default=0.0
)

rgb_shadow_clipping = first_value(
    rgb_clipping,
    [
        "shadow_percent",
        "shadow_clipping_percent",
        "shadow_clipping",
    ],
    default=0.0
)

rgb_highlight_clipping = first_value(
    rgb_clipping,
    [
        "highlight_percent",
        "highlight_clipping_percent",
        "highlight_clipping",
    ],
    default=0.0
)


# ============================================================
# VALORES PRINCIPALES
# ============================================================

raw_mean = safe_float(
    first_value(
        raw_statistics,
        ["mean", "mean_luminance"],
        0.0
    )
)

raw_median = safe_float(
    first_value(
        raw_statistics,
        ["median", "median_luminance"],
        0.0
    )
)

raw_p01 = safe_float(
    first_value(
        raw_statistics,
        ["p01"],
        0.0
    )
)

raw_p99 = safe_float(
    first_value(
        raw_statistics,
        ["p99"],
        0.0
    )
)


rgb_mean = safe_float(
    first_value(
        rgb_luminance,
        ["mean", "mean_luminance"],
        0.0
    )
)

rgb_median = safe_float(
    first_value(
        rgb_luminance,
        ["median", "median_luminance"],
        0.0
    )
)

rgb_p01 = safe_float(
    first_value(
        rgb_luminance,
        ["p01"],
        0.0
    )
)

rgb_p99 = safe_float(
    first_value(
        rgb_luminance,
        ["p99"],
        0.0
    )
)


# ============================================================
# COLOR
# ============================================================

color_cast = rgb_rendered.get(
    "color_cast",
    "UNKNOWN"
)

green_difference = safe_float(
    first_value(
        rgb_rendered,
        [
            "green_dominance",
            "green_difference",
        ],
        0.0
    )
)


# ============================================================
# SPATIAL RAW
# ============================================================

raw_region_count = safe_int(
    first_value(
        raw_spatial_summary,
        ["region_count"],
        0
    )
)

raw_darkest_region = safe_float(
    first_value(
        raw_spatial_summary,
        ["darkest_region_mean"],
        0.0
    )
)

raw_brightest_region = safe_float(
    first_value(
        raw_spatial_summary,
        ["brightest_region_mean"],
        0.0
    )
)

raw_classification_counts = raw_spatial_summary.get(
    "classification_counts",
    {}
)


# ============================================================
# SPATIAL RGB
# ============================================================

rgb_region_count = safe_int(
    first_value(
        rgb_spatial_summary,
        ["region_count"],
        0
    )
)

rgb_darkest_region = safe_float(
    first_value(
        rgb_spatial_summary,
        ["darkest_region_mean"],
        0.0
    )
)

rgb_brightest_region = safe_float(
    first_value(
        rgb_spatial_summary,
        ["brightest_region_mean"],
        0.0
    )
)

rgb_classification_counts = rgb_spatial_summary.get(
    "classification_counts",
    {}
)


# ============================================================
# SPATIAL COLOR
# ============================================================

green_regions = safe_int(
    first_value(
        spatial_color_summary,
        [
            "green_dominant_regions",
            "green_regions",
        ],
        0
    )
)

red_regions = safe_int(
    first_value(
        spatial_color_summary,
        [
            "red_dominant_regions",
            "red_regions",
        ],
        0
    )
)

blue_regions = safe_int(
    first_value(
        spatial_color_summary,
        [
            "blue_dominant_regions",
            "blue_regions",
        ],
        0
    )
)

balanced_regions = safe_int(
    first_value(
        spatial_color_summary,
        ["balanced_regions"],
        0
    )
)

green_fraction = safe_float(
    first_value(
        spatial_color_summary,
        ["green_dominant_fraction"],
        0.0
    )
)

green_distribution = spatial_color_summary.get(
    "green_distribution",
    "UNKNOWN"
)

possible_global_green_cast = bool(
    spatial_color_summary.get(
        "possible_global_green_cast",
        False
    )
)

possible_global_red_cast = bool(
    spatial_color_summary.get(
        "possible_global_red_cast",
        False
    )
)

possible_global_blue_cast = bool(
    spatial_color_summary.get(
        "possible_global_blue_cast",
        False
    )
)


# ============================================================
# RESUMEN OBJETIVO
# ============================================================

measurement_summary = {
    "RAW": {
        "mean": raw_mean,
        "median": raw_median,
        "p01": raw_p01,
        "p99": raw_p99,
        "shadow_clipping_percent": raw_shadow_clipping,
        "highlight_clipping_percent": raw_highlight_clipping,
        "warning": raw_sensor.get(
            "warning",
            "UNKNOWN"
        ),
    },

    "RAW_SPATIAL": {
        "region_count": raw_region_count,
        "darkest_region_mean": raw_darkest_region,
        "brightest_region_mean": raw_brightest_region,
        "classification_counts": raw_classification_counts,
    },

    "RGB": {
        "mean_luminance": rgb_mean,
        "median_luminance": rgb_median,
        "p01": rgb_p01,
        "p99": rgb_p99,
        "shadow_clipping_percent": rgb_shadow_clipping,
        "highlight_clipping_percent": rgb_highlight_clipping,
        "color_cast": color_cast,
        "green_difference": green_difference,
    },

    "RGB_SPATIAL": {
        "region_count": rgb_region_count,
        "darkest_region_mean": rgb_darkest_region,
        "brightest_region_mean": rgb_brightest_region,
        "classification_counts": rgb_classification_counts,
    },

    "SPATIAL_COLOR": {
        "region_count": safe_int(
            first_value(
                spatial_color_summary,
                ["region_count"],
                0
            )
        ),
        "mean_green_dominance": safe_float(
            first_value(
                spatial_color_summary,
                ["mean_green_dominance"],
                0.0
            )
        ),
        "green_dominance_std": safe_float(
            first_value(
                spatial_color_summary,
                ["green_dominance_std"],
                0.0
            )
        ),
        "mean_red_dominance": safe_float(
            first_value(
                spatial_color_summary,
                ["mean_red_dominance"],
                0.0
            )
        ),
        "mean_blue_dominance": safe_float(
            first_value(
                spatial_color_summary,
                ["mean_blue_dominance"],
                0.0
            )
        ),
        "green_regions": green_regions,
        "red_regions": red_regions,
        "blue_regions": blue_regions,
        "balanced_regions": balanced_regions,
        "green_fraction": green_fraction,
        "green_distribution": green_distribution,
        "possible_global_green_cast": possible_global_green_cast,
        "possible_global_red_cast": possible_global_red_cast,
        "possible_global_blue_cast": possible_global_blue_cast,
    },
}


print("\n" + "=" * 60)
print("RESUMEN OBJETIVO")
print("=" * 60)

print(
    json.dumps(
        measurement_summary,
        indent=2,
        ensure_ascii=False
    )
)


# ============================================================
# LIMITES DE SEGURIDAD
# ============================================================

SAFETY_LIMITS = {
    "exposure": (-0.5, 0.5),
    "contrast": (-20, 20),
    "highlights": (-30, 30),
    "shadows": (-30, 30),
    "whites": (-20, 20),
    "blacks": (-20, 20),
    "temperature": (-15, 15),
    "tint": (-10, 10),
    "vibrance": (-15, 15),
    "saturation": (-10, 10),
    "clarity": (-10, 10),
    "texture": (-10, 10),
    "sharpening": (-10, 10),
    "noise_reduction": (-10, 10),
    "rotation": (-3, 3),
}


# ============================================================
# PROMPT PARA QWEN
# ============================================================

objective_json = json.dumps(
    measurement_summary,
    indent=2,
    ensure_ascii=False
)

safety_json = json.dumps(
    SAFETY_LIMITS,
    indent=2,
    ensure_ascii=False
)


prompt = f"""
Eres el motor de decisión fotográfica de PHOTOIA.

Tu función NO es inventar ajustes.

Debes analizar:

1. Mediciones objetivas de la fotografía.
2. Análisis visual producido por LLaVA.
3. Distribución espacial de luminosidad.
4. Distribución espacial del color.
5. Evidencia de clipping real.
6. Contexto visual de la escena.

OBJETIVO:

Determinar si la fotografía necesita ajustes y, si los necesita,
hacer solamente ajustes pequeños, seguros y técnicamente justificados.

IMPORTANTE:

El archivo original es un RAW y NO debe modificarse.

La fotografía analizada contiene vegetación.
Una predominancia de verde NO significa automáticamente un problema
de balance de blancos.

NO conviertas automáticamente:
GREEN -> TINT MAGENTA.

Solo recomienda corrección de tint si existe evidencia de un
dominante global y uniforme.

Tampoco debes aumentar exposición simplemente porque los valores
RAW del sensor sean bajos.

Los valores RAW bajos pueden corresponder a contenido oscuro natural
de la escena.

La exposición debe evaluarse principalmente usando:

- clipping RAW
- clipping RGB
- distribución espacial RGB
- luminancia RGB
- análisis visual

DATOS OBJETIVOS:

{objective_json}

ANÁLISIS VISUAL DE LLAVA:

{llava_analysis}

LÍMITES ABSOLUTOS:

{safety_json}

REGLAS IMPORTANTES:

- Nunca exceder los límites.
- Si no existe evidencia clara de un problema, usar 0.
- Preferir MINIMAL sobre cambios innecesarios.
- No hacer correcciones agresivas.
- No corregir automáticamente el verde de vegetación.
- No corregir exposición solamente por el valor medio RAW.
- No usar rotaciones grandes.
- Si 14 o más regiones RGB de 16 son NORMAL, ser extremadamente
  conservador con exposición y contraste.
- Si RGB shadow clipping es cercano a 0%, no levantar sombras
  automáticamente.
- Si RGB highlight clipping es muy bajo, no reducir highlights
  automáticamente.
- Si possible_global_green_cast es false, tint debe ser 0 salvo que
  exista evidencia visual extremadamente clara.
- No confiar ciegamente en los valores recomendados por LLaVA.
- LLaVA es una fuente de percepción visual, no una autoridad absoluta.

RESPONDE EXCLUSIVAMENTE CON JSON VÁLIDO.

FORMATO EXACTO:

{{
  "decision": "MINIMAL",
  "confidence": 0,
  "reason": "explicación breve",
  "adjustments": {{
    "exposure": 0,
    "contrast": 0,
    "highlights": 0,
    "shadows": 0,
    "whites": 0,
    "blacks": 0,
    "temperature": 0,
    "tint": 0,
    "vibrance": 0,
    "saturation": 0,
    "clarity": 0,
    "texture": 0,
    "sharpening": 0,
    "noise_reduction": 0,
    "rotation": 0
  }},
  "changed_parameters": [],
  "notes": "explicación técnica breve"
}}

Los valores deben ser números.
"""


# ============================================================
# LLAMAR A OLLAMA
# ============================================================

print("\n" + "=" * 60)
print("CONSULTANDO QWEN")
print("=" * 60)

payload = {
    "model": MODEL,
    "prompt": prompt,
    "stream": False,
    "format": "json",
    "options": {
        "temperature": 0.1,
        "num_ctx": 4096,
    },
}


try:
    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=600
    )

    response.raise_for_status()

except requests.RequestException as e:
    print("\nERROR: No se pudo conectar con Ollama.")
    print(e)
    raise SystemExit(1)


try:
    result = response.json()
except json.JSONDecodeError:
    print("\nERROR: Ollama no devolvió JSON válido.")
    print(response.text)
    raise SystemExit(1)


raw_response = result.get("response", "")

if not raw_response:
    print("\nERROR: Ollama devolvió una respuesta vacía.")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    raise SystemExit(1)


# ============================================================
# PARSEAR DECISIÓN
# ============================================================

try:
    decision = json.loads(raw_response)

except json.JSONDecodeError:
    print("\nERROR: La respuesta del modelo no contiene JSON válido.")
    print(raw_response)
    raise SystemExit(1)


# ============================================================
# VALIDACIÓN
# ============================================================

ALLOWED_DECISIONS = {
    "MINIMAL",
    "ADJUST",
    "REVIEW",
}

decision_type = decision.get(
    "decision",
    "REVIEW"
)

if decision_type not in ALLOWED_DECISIONS:
    decision_type = "REVIEW"

decision["decision"] = decision_type


confidence = safe_int(
    decision.get("confidence", 0),
    0
)

confidence = max(
    0,
    min(100, confidence)
)

decision["confidence"] = confidence


adjustments = decision.get(
    "adjustments",
    {}
)

if not isinstance(adjustments, dict):
    adjustments = {}


# ============================================================
# APLICAR LIMITES
# ============================================================

validated_adjustments = {}

for parameter, limits in SAFETY_LIMITS.items():

    minimum, maximum = limits

    value = adjustments.get(
        parameter,
        0
    )

    validated_adjustments[parameter] = clamp(
        value,
        minimum,
        maximum
    )


# ============================================================
# REGLAS OBJETIVAS DE SEGURIDAD
# ============================================================

# ------------------------------------------------------------
# REGLA 1:
# Si casi todas las regiones RGB son normales,
# limitar exposición y contraste.
# ------------------------------------------------------------

normal_regions = safe_int(
    rgb_classification_counts.get(
        "NORMAL",
        0
    ),
    0
)

if rgb_region_count >= 16 and normal_regions >= 14:

    validated_adjustments["exposure"] = clamp(
        validated_adjustments["exposure"],
        -0.2,
        0.2
    )

    validated_adjustments["contrast"] = clamp(
        validated_adjustments["contrast"],
        -10,
        10
    )


# ------------------------------------------------------------
# REGLA 2:
# Si prácticamente no existe clipping de sombras RGB,
# no levantar sombras automáticamente.
# ------------------------------------------------------------

if rgb_shadow_clipping <= 0.1:

    if validated_adjustments["shadows"] > 0:
        validated_adjustments["shadows"] = 0


# ------------------------------------------------------------
# REGLA 3:
# Si no existe clipping significativo de highlights,
# no reducir highlights automáticamente.
# ------------------------------------------------------------

if rgb_highlight_clipping < 1.0:

    if validated_adjustments["highlights"] < 0:
        validated_adjustments["highlights"] = 0


# ------------------------------------------------------------
# REGLA 4:
# Si no existe dominante verde global,
# no aplicar tint magenta.
# ------------------------------------------------------------

if not possible_global_green_cast:

    validated_adjustments["tint"] = 0


# ------------------------------------------------------------
# REGLA 5:
# El mismo principio para rojo y azul.
# ------------------------------------------------------------

if not possible_global_red_cast:
    if validated_adjustments["tint"] < 0:
        validated_adjustments["tint"] = 0


# ------------------------------------------------------------
# REGLA 6:
# No aplicar cambios de temperatura grandes sin evidencia.
# ------------------------------------------------------------

validated_adjustments["temperature"] = clamp(
    validated_adjustments["temperature"],
    -10,
    10
)


# ------------------------------------------------------------
# REGLA 7:
# Si no existe clipping importante del sensor,
# no permitir compensaciones agresivas de exposición.
# ------------------------------------------------------------

if raw_highlight_clipping < 1.0:

    validated_adjustments["exposure"] = clamp(
        validated_adjustments["exposure"],
        -0.25,
        0.25
    )


# ============================================================
# CAMBIOS EFECTIVOS
# ============================================================

changed_parameters = []

for parameter, value in validated_adjustments.items():

    if abs(value) > 0.0001:

        if isinstance(value, float):

            if abs(value - round(value)) < 0.0001:
                value_for_output = int(round(value))
            else:
                value_for_output = round(value, 3)

        else:
            value_for_output = value

        validated_adjustments[parameter] = value_for_output

        changed_parameters.append(
            parameter
        )

    else:

        if parameter == "exposure":
            validated_adjustments[parameter] = 0.0
        else:
            validated_adjustments[parameter] = 0


# ============================================================
# SI NO HAY CAMBIOS
# ============================================================

if len(changed_parameters) == 0:

    decision["decision"] = "MINIMAL"

    if not decision.get("reason"):
        decision["reason"] = (
            "No existe evidencia objetiva suficiente para "
            "realizar ajustes."
        )

    if not decision.get("notes"):
        decision["notes"] = (
            "La imagen se mantiene sin modificaciones."
        )


# ============================================================
# CONSTRUIR DECISIÓN FINAL
# ============================================================

decision["adjustments"] = validated_adjustments

decision["changed_parameters"] = changed_parameters


if not decision.get("reason"):
    decision["reason"] = (
        "Decisión generada a partir del análisis objetivo "
        "y visual."
    )

if not decision.get("notes"):
    decision["notes"] = (
        "Los ajustes fueron validados mediante los límites "
        "de seguridad de PHOTOIA."
    )


# ============================================================
# INFORMACIÓN DE AUDITORÍA
# ============================================================

decision["audit"] = {
    "model": MODEL,
    "objective_analysis_used": True,
    "visual_analysis_used": True,
    "original_raw_modified": False,

    "safety_limits_applied": True,

    "raw_shadow_clipping_percent": round(
        raw_shadow_clipping,
        6
    ),

    "raw_highlight_clipping_percent": round(
        raw_highlight_clipping,
        6
    ),

    "rgb_shadow_clipping_percent": round(
        rgb_shadow_clipping,
        6
    ),

    "rgb_highlight_clipping_percent": round(
        rgb_highlight_clipping,
        6
    ),

    "rgb_normal_regions": normal_regions,

    "rgb_total_regions": rgb_region_count,

    "green_distribution": green_distribution,

    "possible_global_green_cast": (
        possible_global_green_cast
    ),
}


# ============================================================
# GUARDAR DECISIÓN
# ============================================================

with open(
    DECISION_FILE,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        decision,
        f,
        indent=2,
        ensure_ascii=False
    )


# ============================================================
# MOSTRAR RESULTADO
# ============================================================

print("\n" + "=" * 60)
print("DECISIÓN FINAL")
print("=" * 60)

print(
    json.dumps(
        decision,
        indent=2,
        ensure_ascii=False
    )
)

print("\n" + "=" * 60)
print("GUARDADO")
print("=" * 60)

print(
    f"Archivo: {DECISION_FILE}"
)

print("\nPHOTOIA completó la etapa de decisión.")