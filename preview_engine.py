import json
from pathlib import Path
from datetime import datetime


# ============================================================
# PHOTOIA - PREVIEW ENGINE
# ============================================================
# Lee validated_decision.json y prepara una instrucción segura
# para la futura integración con Darktable.
#
# IMPORTANTE:
# - NO modifica el NEF original.
# - NO ejecuta Darktable.
# - NO crea XMP.
# - NO aplica ajustes todavía.
# ============================================================


BASE_DIR = Path(__file__).resolve().parent

DECISION_FILE = BASE_DIR / "validated_decision.json"
ANALYSIS_FILE = BASE_DIR / "image_analysis.json"
RAW_FILE = BASE_DIR / "_DSC2125.NEF"

PREVIEW_PLAN_FILE = BASE_DIR / "preview_plan.json"


# ------------------------------------------------------------
# LÍMITES DE SEGURIDAD
# ------------------------------------------------------------

LIMITS = {
    "exposure": (-0.50, 0.50),
    "contrast": (-20.0, 20.0),
    "highlights": (-30.0, 30.0),
    "shadows": (-30.0, 30.0),
    "whites": (-20.0, 20.0),
    "blacks": (-20.0, 20.0),
    "temperature": (-15.0, 15.0),
    "tint": (-10.0, 10.0),
    "vibrance": (-15.0, 15.0),
    "saturation": (-10.0, 10.0),
    "clarity": (-10.0, 10.0),
    "texture": (-10.0, 10.0),
    "sharpening": (-10.0, 10.0),
    "noise_reduction": (-10.0, 10.0),
    "rotation": (-3.0, 3.0),
}


# ------------------------------------------------------------
# UTILIDADES
# ------------------------------------------------------------

def load_json(path):
    if not path.exists():
        raise FileNotFoundError(f"No existe: {path}")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def validate_adjustments(adjustments):
    """
    Verifica que todos los parámetros estén dentro
    de los límites de seguridad.
    """

    validated = {}
    violations = []

    for parameter, (minimum, maximum) in LIMITS.items():

        value = safe_float(adjustments.get(parameter, 0.0))

        if value < minimum:
            violations.append({
                "parameter": parameter,
                "value": value,
                "limit": minimum,
                "reason": "below_minimum"
            })
            value = minimum

        elif value > maximum:
            violations.append({
                "parameter": parameter,
                "value": value,
                "limit": maximum,
                "reason": "above_maximum"
            })
            value = maximum

        validated[parameter] = value

    return validated, violations


def get_changed_parameters(adjustments):
    return [
        parameter
        for parameter, value in adjustments.items()
        if abs(safe_float(value)) > 0.0001
    ]


# ------------------------------------------------------------
# CARGAR DECISIÓN
# ------------------------------------------------------------

print()
print("=" * 60)
print("PHOTOIA - PREVIEW ENGINE")
print("=" * 60)

print()
print("Comprobando archivos...")

if not RAW_FILE.exists():
    print(f"ERROR: No se encontró el RAW:")
    print(RAW_FILE)
    raise SystemExit(1)

print(f"OK RAW: {RAW_FILE.name}")

if not ANALYSIS_FILE.exists():
    print("ERROR: No existe image_analysis.json")
    raise SystemExit(1)

print("OK: image_analysis.json")

if not DECISION_FILE.exists():
    print("ERROR: No existe validated_decision.json")
    print("Ejecuta primero:")
    print("python decision_validator.py")
    raise SystemExit(1)

print("OK: validated_decision.json")


# ------------------------------------------------------------
# LEER DECISIÓN
# ------------------------------------------------------------

decision = load_json(DECISION_FILE)

validation_status = decision.get("validation_status", "")
edit_status = decision.get("edit_status", "")
original_decision = decision.get("original_decision", "")
confidence = safe_float(decision.get("confidence", 0))

adjustments = decision.get("adjustments", {})

if not isinstance(adjustments, dict):
    print("ERROR: 'adjustments' no es un objeto válido.")
    raise SystemExit(1)


# ------------------------------------------------------------
# COMPROBAR ESTADO DE VALIDACIÓN
# ------------------------------------------------------------

print()
print("Estado de validación:")
print(f"  validation_status: {validation_status}")
print(f"  edit_status:       {edit_status}")
print(f"  decision:          {original_decision}")
print(f"  confidence:        {confidence:.0f}")


if validation_status not in {
    "APPROVED",
    "APPROVED_WITH_CORRECTIONS"
}:
    print()
    print("ERROR: La decisión no está aprobada.")
    print("PHOTOIA NO continuará.")
    raise SystemExit(1)


# ------------------------------------------------------------
# VALIDAR AJUSTES NUEVAMENTE
# ------------------------------------------------------------

validated_adjustments, violations = validate_adjustments(adjustments)

if violations:
    print()
    print("ADVERTENCIA: se detectaron valores fuera de límites.")

    for violation in violations:
        print(
            f"  {violation['parameter']}: "
            f"{violation['value']} -> corregido"
        )

else:
    print()
    print("Ajustes dentro de los límites de seguridad.")


# ------------------------------------------------------------
# PARÁMETROS QUE REALMENTE CAMBIARÍAN
# ------------------------------------------------------------

changed_parameters = get_changed_parameters(validated_adjustments)

print()
print("AJUSTES PROPUESTOS")
print("-" * 60)

if changed_parameters:

    for parameter in changed_parameters:
        print(
            f"  {parameter:20s}: "
            f"{validated_adjustments[parameter]:.2f}"
        )

else:
    print("  Ningún ajuste.")

# ------------------------------------------------------------
# DECIDIR SI HAY ALGO QUE PREVISUALIZAR
# ------------------------------------------------------------

if edit_status == "NO_CHANGE" or not changed_parameters:

    preview_status = "NO_PREVIEW_REQUIRED"

else:

    preview_status = "PREVIEW_READY"


# ------------------------------------------------------------
# CREAR PLAN DE PREVIEW
# ------------------------------------------------------------

preview_plan = {
    "photoia": {
        "stage": "PREVIEW_ENGINE",
        "version": "0.1.0"
    },

    "created_at": datetime.now().isoformat(),

    "input": {
        "raw_file": str(RAW_FILE),
        "original_raw_modified": False
    },

    "validation": {
        "validation_status": validation_status,
        "edit_status": edit_status,
        "original_decision": original_decision,
        "confidence": confidence,
        "violations_detected": len(violations)
    },

    "adjustments": validated_adjustments,

    "changed_parameters": changed_parameters,

    "preview": {
        "status": preview_status,
        "darktable_called": False,
        "xmp_created": False,
        "raw_modified": False
    },

    "safety": {
        "original_raw_modified": False,
        "darktable_called": False,
        "automatic_edit_applied": False
    },

    "next_stage": {
        "component": "DARKTABLE_PREVIEW",
        "ready": preview_status == "PREVIEW_READY"
    }
}


# ------------------------------------------------------------
# GUARDADO
# ------------------------------------------------------------

with open(PREVIEW_PLAN_FILE, "w", encoding="utf-8") as f:
    json.dump(
        preview_plan,
        f,
        indent=2,
        ensure_ascii=False
    )


# ------------------------------------------------------------
# RESULTADO
# ------------------------------------------------------------

print()
print("=" * 60)
print("RESULTADO")
print("=" * 60)

print()
print(f"Preview status: {preview_status}")

if changed_parameters:
    print()
    print("PHOTOIA quiere probar estos ajustes:")

    for parameter in changed_parameters:
        print(
            f"  {parameter}: "
            f"{validated_adjustments[parameter]:.2f}"
        )

else:
    print()
    print("No hay ajustes que previsualizar.")

print()
print("Darktable ejecutado: NO")
print("XMP creado:          NO")
print("RAW modificado:      NO")

print()
print(f"Archivo generado:")
print(PREVIEW_PLAN_FILE)

print()
print("PHOTOIA completó la etapa PREVIEW ENGINE.")