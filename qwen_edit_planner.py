import base64
import io
import json
import math
import os
import re

import requests
from PIL import Image
from apply.writers.sigmoid import unpack_sigmoid_params


# ============================================================
# PHOTOIA - QWEN EDIT PLANNER
#
# Qwen analiza la fotografía y propone cambios para Sigmoid.
#
# IMPORTANTE:
#   - NO modifica XMP.
#   - NO modifica edit_plan.json.
#   - Genera edit_plan_proposed.json.
# ============================================================


MODEL = "qwen2.5vl:7b"

IMAGE_FILE = "_DSC2125.JPG"
XMP_FILE = "_DSC2125.NEF.xmp"

OUTPUT_FILE = "edit_plan_proposed.json"

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"


COLOR_PROCESSING = {
    0: "per channel",
    1: "RGB ratio",
}

BASE_PRIMARIES = {
    0: "working profile",
    1: "Rec2020",
    2: "Display P3",
    3: "Adobe RGB (compatible)",
    4: "sRGB",
}


# ============================================================
# LEER EL ULTIMO SIGMOID
# ============================================================

def extract_latest_sigmoid():

    import re

    if not os.path.exists(XMP_FILE):

        raise RuntimeError(
            f"No existe {XMP_FILE}"
        )

    with open(
        XMP_FILE,
        "r",
        encoding="utf-8"
    ) as f:

        xmp = f.read()

    pattern = re.compile(
        r'<rdf:li\b'
        r'(?P<attrs>[^>]*)'
        r'darktable:operation="sigmoid"'
        r'(?P<attrs2>[^>]*)'
        r'darktable:params="(?P<params>[0-9a-fA-F]+)"'
        r'[^>]*>',
        re.S,
    )

    results = []

    for match in pattern.finditer(xmp):

        attrs = (
            match.group("attrs")
            + match.group("attrs2")
        )

        num_match = re.search(
            r'darktable:num="(\d+)"',
            attrs
        )

        if not num_match:
            continue

        num = int(
            num_match.group(1)
        )

        params = match.group("params")

        raw = bytes.fromhex(
            params
        )

        if len(raw) != 56:
            continue

        values = unpack_sigmoid_params(raw)

        results.append(
            {
                "num": num,
                "values": values,
            }
        )

    if not results:

        raise RuntimeError(
            "No se encontró ningún Sigmoid válido."
        )

    results.sort(
        key=lambda item: item["num"]
    )

    return results[-1]


# ============================================================
# SIGMOID INTERNO -> VALORES HUMANOS
# ============================================================

def sigmoid_to_ui(item):

    v = item["values"]

    return {
        "contrast": v[0],
        "skew": v[1],

        "target_white": v[2],
        "target_black": v[3],

        "color_processing":
            COLOR_PROCESSING.get(
                int(round(v[4])),
                "UNKNOWN"
            ),

        # IMPORTANTE:
        # Preserve hue está almacenado directamente
        # en la escala 0-100.
        "preserve_hue": v[5],

        "red_attenuation": v[6] * 100.0,
        "red_rotation": math.degrees(v[7]),

        "green_attenuation": v[8] * 100.0,
        "green_rotation": math.degrees(v[9]),

        "blue_attenuation": v[10] * 100.0,
        "blue_rotation": math.degrees(v[11]),

        "recover_purity": v[12] * 100.0,

        "base_primaries":
            BASE_PRIMARIES.get(
                int(round(v[13])),
                "UNKNOWN"
            ),
    }


# ============================================================
# CARGAR IMAGEN
# ============================================================

def load_image_base64():

    if not os.path.exists(IMAGE_FILE):

        raise RuntimeError(
            f"No existe la imagen: {IMAGE_FILE}"
        )

    with Image.open(IMAGE_FILE) as img:
        img = img.convert("RGB")
        w, h = img.size
        max_size = 1024
        if max(w, h) > max_size:
            scale = max_size / max(w, h)
            new_size = (int(round(w * scale)), int(round(h * scale)))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")


# ============================================================
# PROMPT
# ============================================================

def build_prompt(current_state):

    current_num = current_state["darktable_num"]

    current_sigmoid = current_state["sigmoid"]

    current_json = json.dumps(
        current_sigmoid,
        indent=2,
        ensure_ascii=False
    )

    return f"""
Analiza la fotografía adjunta como un fotógrafo profesional.

Tu objetivo es proponer una mejora MODERADA del módulo Sigmoid
de Darktable.

Primero observa la fotografía y determina visualmente:

- exposición y contraste global;
- recuperación de altas luces;
- profundidad de negros;
- dominantes de color;
- saturación o pérdida de color;
- posibles problemas de separación RGB;
- si el procesamiento actual parece razonable.

ESTADO ACTUAL DEL SIGMOID

darktable_num = {current_num}

{current_json}

REGLA PRINCIPAL:

El estado actual es tu PUNTO DE PARTIDA.

NO reemplaces los valores actuales por ceros.

Cada valor propuesto debe comenzar siendo igual al valor actual.

Solo cambia un parámetro cuando exista una razón visual
clara para hacerlo.

Para cambios pequeños usa ajustes pequeños.

Evita cambios agresivos.

Devuelve SOLO JSON válido.

La estructura debe ser exactamente:

{{
  "version": 1,
  "target": {{
    "operation": "sigmoid",
    "darktable_num": {current_num}
  }},
  "sigmoid": {current_json}
}}

REGLAS DE LOS PARAMETROS:

contrast:
0.0 a 10.0

skew:
-1.0 a 1.0

target_white:
0.0 a 100.0

target_black:
0.0 a 100.0

preserve_hue:
0.0 a 100.0

red_attenuation:
0.0 a 100.0

red_rotation:
-360.0 a 360.0

green_attenuation:
0.0 a 100.0

green_rotation:
-360.0 a 360.0

blue_attenuation:
0.0 a 100.0

blue_rotation:
-360.0 a 360.0

recover_purity:
0.0 a 100.0

color_processing:
"per channel" o "RGB ratio"

base_primaries:
"working profile"
"Rec2020"
"Display P3"
"Adobe RGB (compatible)"
"sRGB"

IMPORTANTE:

1. No cambies todos los controles.
2. Conserva los valores actuales cuando no haya una razón clara.
3. No uses 0 como valor por defecto.
4. No inventes problemas que no puedas observar.
5. No hagas cambios extremos.
6. No incluyas markdown.
7. No incluyas explicaciones fuera del JSON.
8. Devuelve solamente el objeto JSON.
"""


# ============================================================
# EXTRAER JSON
# ============================================================

def extract_json(text):

    text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass

    match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.S,
    )

    if match:

        return json.loads(
            match.group(1)
        )

    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:

        return json.loads(
            text[start:end + 1]
        )

    raise RuntimeError(
        "No se encontró JSON válido."
    )


# ============================================================
# VALIDAR PROPUESTA
# ============================================================

def validate_plan(
    plan,
    current_num
):

    if not isinstance(plan, dict):

        raise RuntimeError(
            "La propuesta no es un objeto JSON."
        )

    if plan.get("version") != 1:

        raise RuntimeError(
            "version debe ser 1."
        )

    target = plan.get("target")

    if not isinstance(
        target,
        dict
    ):

        raise RuntimeError(
            "Falta target."
        )

    if target.get("operation") != "sigmoid":

        raise RuntimeError(
            "target.operation debe ser sigmoid."
        )

    if target.get(
        "darktable_num"
    ) != current_num:

        raise RuntimeError(
            "Qwen intentó modificar otro "
            "darktable:num."
        )

    sigmoid = plan.get("sigmoid")

    if not isinstance(
        sigmoid,
        dict
    ):

        raise RuntimeError(
            "Falta sigmoid."
        )

    required = [
        "contrast",
        "skew",
        "target_white",
        "target_black",
        "color_processing",
        "preserve_hue",
        "red_attenuation",
        "red_rotation",
        "green_attenuation",
        "green_rotation",
        "blue_attenuation",
        "blue_rotation",
        "recover_purity",
        "base_primaries",
    ]

    for field in required:

        if field not in sigmoid:

            raise RuntimeError(
                f"Falta {field}."
            )

    ranges = {
        "contrast": (0.0, 10.0),
        "skew": (-1.0, 1.0),
        "target_white": (0.0, 100.0),
        "target_black": (0.0, 100.0),
        "preserve_hue": (0.0, 100.0),
        "red_attenuation": (0.0, 100.0),
        "green_attenuation": (0.0, 100.0),
        "blue_attenuation": (0.0, 100.0),
        "recover_purity": (0.0, 100.0),
        "red_rotation": (-360.0, 360.0),
        "green_rotation": (-360.0, 360.0),
        "blue_rotation": (-360.0, 360.0),
    }

    for field, (
        minimum,
        maximum
    ) in ranges.items():

        value = sigmoid[field]

        if not isinstance(
            value,
            (int, float)
        ):

            raise RuntimeError(
                f"{field} debe ser numérico."
            )

        if not (
            minimum
            <= float(value)
            <= maximum
        ):

            raise RuntimeError(
                f"{field} fuera de rango: "
                f"{value}"
            )

    if sigmoid[
        "color_processing"
    ] not in (
        "per channel",
        "RGB ratio",
    ):

        raise RuntimeError(
            "color_processing inválido."
        )

    if sigmoid[
        "base_primaries"
    ] not in BASE_PRIMARIES.values():

        raise RuntimeError(
            "base_primaries inválido."
        )


# ============================================================
# COMPARAR CON EL ESTADO ACTUAL
# ============================================================

def show_changes(
    current,
    proposed
):

    print()
    print("=" * 78)
    print("CAMBIOS PROPUESTOS POR QWEN")
    print("=" * 78)

    changes = []

    numeric_fields = [
        "contrast",
        "skew",
        "target_white",
        "target_black",
        "preserve_hue",
        "red_attenuation",
        "red_rotation",
        "green_attenuation",
        "green_rotation",
        "blue_attenuation",
        "blue_rotation",
        "recover_purity",
    ]

    for field in numeric_fields:

        old = float(
            current[field]
        )

        new = float(
            proposed[field]
        )

        if abs(old - new) > 0.0001:

            changes.append(
                (
                    field,
                    old,
                    new,
                    new - old,
                )
            )

    enum_fields = [
        "color_processing",
        "base_primaries",
    ]

    for field in enum_fields:

        old = current[field]
        new = proposed[field]

        if old != new:

            changes.append(
                (
                    field,
                    old,
                    new,
                    None,
                )
            )

    if not changes:

        print()
        print(
            "Qwen no propuso cambios."
        )

        return

    for item in changes:

        field, old, new, delta = item

        print()

        print(
            f"{field}:"
        )

        print(
            f"  actual:    {old}"
        )

        print(
            f"  propuesto: {new}"
        )

        if delta is not None:

            print(
                f"  delta:     {delta:+.6f}"
            )

    print()
    print(
        f"Controles modificados: "
        f"{len(changes)}"
    )


# ============================================================
# CONSULTAR OLLAMA
# ============================================================

def ask_qwen(
    prompt,
    image_base64
):

    payload = {
        "model": MODEL,
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [
                    image_base64
                ],
            }
        ],
        "options": {
            "temperature": 0.1,
            "num_ctx": 8192,
        },
    }

    print()
    print(
        f"Enviando fotografía a {MODEL}..."
    )

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=600,
    )

    if response.status_code != 200:

        print()
        print(
            "ERROR HTTP DE OLLAMA"
        )

        print(
            f"HTTP: {response.status_code}"
        )

        print()

        print(
            response.text
        )

        raise RuntimeError(
            "Ollama rechazó la solicitud."
        )

    data = response.json()

    message = data.get(
        "message"
    )

    if not isinstance(
        message,
        dict
    ):

        raise RuntimeError(
            "Respuesta de Ollama sin message."
        )

    content = message.get(
        "content"
    )

    if not isinstance(
        content,
        str
    ):

        raise RuntimeError(
            "Respuesta de Ollama sin content."
        )

    return content


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 78)
    print("PHOTOIA - QWEN EDIT PLANNER")
    print("=" * 78)

    # --------------------------------------------------------
    # ESTADO ACTUAL
    # --------------------------------------------------------

    current_raw = extract_latest_sigmoid()

    current_sigmoid = sigmoid_to_ui(
        current_raw
    )

    current_num = current_raw["num"]

    print()
    print(
        f"Sigmoid actual: num={current_num}"
    )

    print()
    print(
        "Estado actual:"
    )

    print(
        json.dumps(
            current_sigmoid,
            indent=2,
            ensure_ascii=False
        )
    )

    # --------------------------------------------------------
    # IMAGEN
    # --------------------------------------------------------

    image_base64 = load_image_base64()

    # --------------------------------------------------------
    # PROMPT
    # --------------------------------------------------------

    prompt = build_prompt(
        {
            "darktable_num": current_num,
            "sigmoid": current_sigmoid,
        }
    )

    # --------------------------------------------------------
    # QWEN
    # --------------------------------------------------------

    try:

        response_text = ask_qwen(
            prompt,
            image_base64
        )

    except requests.exceptions.ConnectionError:

        print()
        print(
            "ERROR: No se pudo conectar con Ollama."
        )

        return 1

    except requests.exceptions.Timeout:

        print()
        print(
            "ERROR: Ollama agotó el tiempo."
        )

        return 1

    except RuntimeError as error:

        print()
        print(
            f"ERROR: {error}"
        )

        return 1

    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    print()
    print(
        "Procesando respuesta de Qwen..."
    )

    try:

        plan = extract_json(
            response_text
        )

        validate_plan(
            plan,
            current_num
        )

    except (
        json.JSONDecodeError,
        RuntimeError,
        ValueError
    ) as error:

        print()
        print(
            "ERROR: propuesta inválida."
        )

        print()
        print(
            error
        )

        print()
        print(
            "RESPUESTA DE QWEN:"
        )

        print(
            response_text
        )

        return 1

    # --------------------------------------------------------
    # MOSTRAR CAMBIOS
    # --------------------------------------------------------

    show_changes(
        current_sigmoid,
        plan["sigmoid"]
    )

    # --------------------------------------------------------
    # GUARDAR
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            plan,
            f,
            indent=2,
            ensure_ascii=False
        )

        f.write("\n")

    # --------------------------------------------------------
    # RESULTADO
    # --------------------------------------------------------

    print()
    print("=" * 78)
    print("PROPUESTA GENERADA")
    print("=" * 78)

    print()
    print(
        f"Archivo: {OUTPUT_FILE}"
    )

    print()
    print(
        "Qwen NO modificó el XMP."
    )

    print(
        "Qwen NO modificó edit_plan.json."
    )

    print(
        "Solo generó una propuesta."
    )

    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
