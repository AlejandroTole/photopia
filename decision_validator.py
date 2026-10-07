import json
import os
import sys


# ============================================================
# PHOTOIA - DECISION VALIDATOR
# Valida la decisión de la IA antes de permitir cualquier edición
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ANALYSIS_FILE = os.path.join(BASE_DIR, "image_analysis.json")
DECISION_FILE = os.path.join(BASE_DIR, "photo_decision.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "validated_decision.json")


# ============================================================
# LÍMITES DE SEGURIDAD
# ============================================================

LIMITS = {
    "exposure": 0.50,
    "contrast": 20,
    "highlights": 30,
    "shadows": 30,
    "whites": 20,
    "blacks": 20,
    "temperature": 15,
    "tint": 10,
    "vibrance": 15,
    "saturation": 10,
    "clarity": 10,
    "texture": 10,
    "sharpening": 10,
    "noise_reduction": 10,
    "rotation": 3,
}


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def load_json(path):
    if not os.path.exists(path):
        print(f"ERROR: No existe {path}")
        sys.exit(1)

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"ERROR leyendo {path}: {e}")
        sys.exit(1)


def get_value(data, *keys, default=0.0):
    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default

        if key not in current:
            return default

        current = current[key]

    return safe_float(current, default)


# ============================================================
# VALIDACIÓN DE AJUSTES
# ============================================================

def validate_limits(adjustments):
    violations = []
    corrected = {}

    for parameter, limit in LIMITS.items():

        value = safe_float(adjustments.get(parameter, 0.0))

        if abs(value) > limit:
            violations.append({
                "parameter": parameter,
                "requested": value,
                "limit": limit,
                "action": "CLAMPED"
            })

            value = clamp(value, -limit, limit)

        corrected[parameter] = value

    return corrected, violations


# ============================================================
# REGLAS FOTOGRÁFICAS
# ============================================================

def validate_photographic_logic(adjustments, analysis):

    violations = []

    raw = analysis.get("raw_sensor", {})
    rgb = analysis.get("rgb_rendered", {})

    raw_clip = raw.get("clipping", {})
    rgb_clip = rgb.get("clipping", {})

    raw_shadow = safe_float(raw_clip.get("shadow_percent"))
    raw_highlight = safe_float(raw_clip.get("highlight_percent"))

    rgb_shadow = safe_float(rgb_clip.get("shadow_percent"))
    rgb_highlight = safe_float(rgb_clip.get("highlight_percent"))

    rgb_spatial = rgb.get("spatial_analysis", {})
    rgb_summary = rgb_spatial.get("summary", {})

    normal_regions = rgb_summary.get(
        "classification_counts", {}
    ).get("NORMAL", 0)

    total_regions = rgb_summary.get("region_count", 0)

    spatial_color = rgb.get("spatial_color_analysis", {})
    color_summary = spatial_color.get("summary", {})

    global_green_cast = bool(
        color_summary.get("possible_global_green_cast", False)
    )

    global_red_cast = bool(
        color_summary.get("possible_global_red_cast", False)
    )

    global_blue_cast = bool(
        color_summary.get("possible_global_blue_cast", False)
    )

    # --------------------------------------------------------
    # EXPOSURE
    # --------------------------------------------------------

    exposure = safe_float(adjustments.get("exposure"))

    if raw_highlight < 1.0 and exposure < -0.25:
        violations.append({
            "parameter": "exposure",
            "requested": exposure,
            "reason": (
                "RAW highlight clipping is below 1%; "
                "there is no objective evidence requiring "
                "a strong exposure reduction."
            ),
            "action": "LIMITED"
        })

        adjustments["exposure"] = -0.25

    if rgb_shadow <= 0.1 and exposure > 0.25:
        violations.append({
            "parameter": "exposure",
            "requested": exposure,
            "reason": (
                "RGB shadow clipping is negligible; "
                "strong exposure increase is not objectively justified."
            ),
            "action": "LIMITED"
        })

        adjustments["exposure"] = 0.25

    # --------------------------------------------------------
    # HIGHLIGHTS
    # --------------------------------------------------------

    highlights = safe_float(adjustments.get("highlights"))

    if rgb_highlight < 1.0 and highlights < -10:
        violations.append({
            "parameter": "highlights",
            "requested": highlights,
            "reason": (
                "RGB highlight clipping is below 1%; "
                "strong highlight reduction is not justified."
            ),
            "action": "LIMITED"
        })

        adjustments["highlights"] = -10

    # --------------------------------------------------------
    # SHADOWS
    # --------------------------------------------------------

    shadows = safe_float(adjustments.get("shadows"))

    if rgb_shadow <= 0.1 and shadows > 15:
        violations.append({
            "parameter": "shadows",
            "requested": shadows,
            "reason": (
                "RGB shadow clipping is negligible; "
                "large shadow lifting is not objectively required."
            ),
            "action": "LIMITED"
        })

        adjustments["shadows"] = 15

    # --------------------------------------------------------
    # CONTRAST
    # --------------------------------------------------------

    contrast = safe_float(adjustments.get("contrast"))

    if total_regions >= 14 and normal_regions >= 14:
        if abs(contrast) > 10:
            violations.append({
                "parameter": "contrast",
                "requested": contrast,
                "reason": (
                    "At least 14/16 RGB regions are normal; "
                    "strong contrast changes are unnecessary."
                ),
                "action": "LIMITED"
            })

            adjustments["contrast"] = clamp(
                contrast,
                -10,
                10
            )

    # --------------------------------------------------------
    # COLOR TEMPERATURE
    # --------------------------------------------------------

    temperature = safe_float(adjustments.get("temperature"))

    if abs(temperature) > 10:
        violations.append({
            "parameter": "temperature",
            "requested": temperature,
            "reason": "Temperature adjustment exceeds conservative limit.",
            "action": "LIMITED"
        })

        adjustments["temperature"] = clamp(
            temperature,
            -10,
            10
        )

    # --------------------------------------------------------
    # TINT
    # --------------------------------------------------------

    tint = safe_float(adjustments.get("tint"))

    if not global_green_cast and not global_red_cast and not global_blue_cast:

        if abs(tint) > 0:
            violations.append({
                "parameter": "tint",
                "requested": tint,
                "reason": (
                    "Spatial color analysis does not detect a global "
                    "color cast."
                ),
                "action": "RESET"
            })

            adjustments["tint"] = 0.0

    # --------------------------------------------------------
    # SHARPENING
    # --------------------------------------------------------

    sharpening = safe_float(adjustments.get("sharpening"))

    if sharpening > 10:
        violations.append({
            "parameter": "sharpening",
            "requested": sharpening,
            "reason": "Sharpening is intentionally conservative.",
            "action": "LIMITED"
        })

        adjustments["sharpening"] = 10

    # --------------------------------------------------------
    # ROTATION
    # --------------------------------------------------------

    rotation = safe_float(adjustments.get("rotation"))

    if abs(rotation) > 3:
        violations.append({
            "parameter": "rotation",
            "requested": rotation,
            "reason": (
                "Large automatic rotation is unsafe without "
                "explicit horizon detection."
            ),
            "action": "LIMITED"
        })

        adjustments["rotation"] = clamp(
            rotation,
            -3,
            3
        )

    return adjustments, violations


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 60)
    print("PHOTOIA - DECISION VALIDATOR")
    print("=" * 60)

    print("\nCargando análisis objetivo...")
    analysis = load_json(ANALYSIS_FILE)
    print("OK: image_analysis.json")

    print("\nCargando decisión...")
    decision = load_json(DECISION_FILE)
    print("OK: photo_decision.json")

    adjustments = decision.get("adjustments", {})

    print("\n" + "=" * 60)
    print("DECISIÓN RECIBIDA")
    print("=" * 60)

    print(
        json.dumps(
            {
                "decision": decision.get("decision"),
                "confidence": decision.get("confidence"),
                "adjustments": adjustments
            },
            indent=2,
            ensure_ascii=False
        )
    )

    # --------------------------------------------------------
    # 1. VALIDAR LÍMITES GENERALES
    # --------------------------------------------------------

    validated_adjustments, limit_violations = validate_limits(
        adjustments
    )

    # --------------------------------------------------------
    # 2. VALIDAR LÓGICA FOTOGRÁFICA
    # --------------------------------------------------------

    validated_adjustments, logic_violations = (
        validate_photographic_logic(
            validated_adjustments,
            analysis
        )
    )

    violations = limit_violations + logic_violations

    # --------------------------------------------------------
    # 3. DETERMINAR RESULTADO
    # --------------------------------------------------------

    if len(violations) == 0:
        validation_status = "APPROVED"
    else:
        validation_status = "APPROVED_WITH_CORRECTIONS"

    # --------------------------------------------------------
    # 4. DETERMINAR SI HAY CAMBIOS
    # --------------------------------------------------------

    changed_parameters = []

    for parameter, value in validated_adjustments.items():

        if abs(safe_float(value)) > 0.0001:
            changed_parameters.append(parameter)

    if len(changed_parameters) == 0:
        edit_status = "NO_CHANGE"
    else:
        edit_status = "EDIT_REQUIRED"

    # --------------------------------------------------------
    # 5. CREAR RESULTADO
    # --------------------------------------------------------

    result = {
        "validation_status": validation_status,
        "edit_status": edit_status,
        "original_decision": decision.get("decision"),
        "confidence": decision.get("confidence"),
        "adjustments": validated_adjustments,
        "changed_parameters": changed_parameters,
        "violations": violations,
        "audit": {
            "validator": "PHOTOIA_DECISION_VALIDATOR",
            "objective_analysis_used": True,
            "safety_limits_applied": True,
            "original_raw_modified": False,
            "darktable_called": False
        }
    }

    # --------------------------------------------------------
    # 6. GUARDAR
    # --------------------------------------------------------

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            result,
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # 7. MOSTRAR RESULTADO
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print("RESULTADO DE VALIDACIÓN")
    print("=" * 60)

    print(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        )
    )

    print("\n" + "=" * 60)
    print("GUARDADO")
    print("=" * 60)

    print(f"Archivo: {OUTPUT_FILE}")

    print("\nPHOTOIA completó la validación.")
    print("Darktable NO fue ejecutado.")
    print("El archivo RAW original NO fue modificado.")


if __name__ == "__main__":
    main()