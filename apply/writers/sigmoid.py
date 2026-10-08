"""
PHOTOIA - Sigmoid Writer (v2)
Sigmoid enum slots 4 and 13 use int32; the remaining slots use float32.
"""
from pathlib import Path
import math
import struct
from typing import Any, Dict, Optional, Sequence, Tuple

from apply.xmp import (
    read_xmp,
    find_operation_modules,
    select_target_module,
    replace_module_params,
    create_backup,
    restore_backup,
    atomic_write,
)

SIGMOID_BYTES_LEN = 56
SIGMOID_PARAM_COUNT = 14
SLOT_COLOR_PROCESSING = 4
SLOT_BASE_PRIMARIES = 13

PARAM_NAMES = [
    "contrast",               # [0] float
    "skew",                   # [1] float
    "target_white",           # [2] float
    "target_black",           # [3] float
    "color_processing",       # [4] int enum (0: per channel, 1: RGB ratio)
    "preserve_hue",           # [5] float (0.0..100.0)
    "red_attenuation",        # [6] float (internal fraction 0..0.99)
    "red_rotation",           # [7] float (internal radians -0.4..0.4)
    "green_attenuation",      # [8] float (internal fraction 0..0.99)
    "green_rotation",         # [9] float (internal radians -0.4..0.4)
    "blue_attenuation",       # [10] float (internal fraction 0..0.99)
    "blue_rotation",          # [11] float (internal radians -0.4..0.4)
    "recover_purity",         # [12] float (internal fraction 0..1.0)
    "base_primaries",         # [13] int enum (0: working profile, 1: Rec2020, 2: Display P3, 3: Adobe RGB, 4: sRGB)
]

COLOR_PROCESSING_MAP = {
    "per channel": 0,
    "RGB ratio": 1,
}
COLOR_PROCESSING_REV = {v: k for k, v in COLOR_PROCESSING_MAP.items()}

BASE_PRIMARIES_MAP = {
    "working profile": 0,
    "Rec2020": 1,
    "Display P3": 2,
    "Adobe RGB (compatible)": 3,
    "sRGB": 4,
}
BASE_PRIMARIES_REV = {v: k for k, v in BASE_PRIMARIES_MAP.items()}

SIGMOID_ENUM_RANGES = {
    SLOT_COLOR_PROCESSING: range(2),
    SLOT_BASE_PRIMARIES: range(5),
}


def _enum_value(index: int, value: Any) -> int:
    try:
        numeric_value = float(value)
    except (OverflowError, TypeError, ValueError) as error:
        raise ValueError(f"El slot sigmoid {index} debe ser un enum entero.") from error
    if not numeric_value.is_integer():
        raise ValueError(f"El slot sigmoid {index} debe ser un enum entero.")

    enum_value = int(numeric_value)
    if enum_value not in SIGMOID_ENUM_RANGES[index]:
        allowed = ", ".join(str(item) for item in SIGMOID_ENUM_RANGES[index])
        raise ValueError(f"El slot sigmoid {index} debe ser uno de: {allowed}.")
    return enum_value


def unpack_sigmoid_params(raw: bytes) -> Tuple[Any, ...]:
    if len(raw) != SIGMOID_BYTES_LEN:
        raise ValueError(f"Se esperaban {SIGMOID_BYTES_LEN} bytes, se recibieron {len(raw)}")

    values = []
    for index in range(SIGMOID_PARAM_COUNT):
        start = index * 4
        slot = raw[start:start + 4]
        if index in SIGMOID_ENUM_RANGES:
            values.append(_enum_value(index, struct.unpack("<i", slot)[0]))
        else:
            values.append(struct.unpack("<f", slot)[0])
    return tuple(values)


def pack_sigmoid_params(values: Sequence[Any]) -> bytes:
    if len(values) != SIGMOID_PARAM_COUNT:
        raise ValueError(f"Sigmoid requiere {SIGMOID_PARAM_COUNT} parámetros.")

    packed_slots = []
    for index, value in enumerate(values):
        if index in SIGMOID_ENUM_RANGES:
            packed_slots.append(struct.pack("<i", _enum_value(index, value)))
        else:
            packed_slots.append(struct.pack("<f", float(value)))

    raw = b"".join(packed_slots)
    if len(raw) != SIGMOID_BYTES_LEN:
        raise RuntimeError(f"El sigmoid debe ocupar exactamente {SIGMOID_BYTES_LEN} bytes.")
    return raw


def decode_sigmoid_hex(hex_data: str) -> Dict[str, Any]:
    raw = bytes.fromhex(hex_data)
    values = unpack_sigmoid_params(raw)

    return {
        "contrast": values[0],
        "skew": values[1],
        "target_white": values[2],
        "target_black": values[3],
        "color_processing": values[4],
        "preserve_hue": values[5],
        "red_attenuation_ui": values[6] * 100.0,
        "red_rotation_ui": math.degrees(values[7]),
        "green_attenuation_ui": values[8] * 100.0,
        "green_rotation_ui": math.degrees(values[9]),
        "blue_attenuation_ui": values[10] * 100.0,
        "blue_rotation_ui": math.degrees(values[11]),
        "recover_purity_ui": values[12] * 100.0,
        "base_primaries": values[13],
        # Raw internal values
        "raw_tuple": values,
    }


def encode_sigmoid(params: Dict[str, Any]) -> str:
    """
    Pack dictionary values into the mixed int32/float32 XMP layout.
    """
    color_proc = params.get("color_processing", 0)
    if isinstance(color_proc, str):
        try:
            color_proc = COLOR_PROCESSING_MAP[color_proc]
        except KeyError as error:
            raise ValueError(f"color_processing inválido: {color_proc}") from error

    base_prim = params.get("base_primaries", 0)
    if isinstance(base_prim, str):
        try:
            base_prim = BASE_PRIMARIES_MAP[base_prim]
        except KeyError as error:
            raise ValueError(f"base_primaries inválido: {base_prim}") from error

    color_proc = _enum_value(SLOT_COLOR_PROCESSING, color_proc)
    base_prim = _enum_value(SLOT_BASE_PRIMARIES, base_prim)

    # Conversion from UI units if present, else internal
    def get_percent(key_ui, key_internal, default=0.0):
        if key_ui in params:
            return float(params[key_ui]) / 100.0
        return float(params.get(key_internal, default))

    def get_rad(key_ui, key_internal, default=0.0):
        if key_ui in params:
            return math.radians(float(params[key_ui]))
        return float(params.get(key_internal, default))

    raw_values = (
        float(params["contrast"]),
        float(params["skew"]),
        float(params.get("target_white", 100.0)),
        float(params.get("target_black", 0.0152)),
        int(color_proc),
        float(params.get("preserve_hue", 100.0)),
        get_percent("red_attenuation_ui", "red_attenuation", 0.0),
        get_rad("red_rotation_ui", "red_rotation", 0.0),
        get_percent("green_attenuation_ui", "green_attenuation", 0.0),
        get_rad("green_rotation_ui", "green_rotation", 0.0),
        get_percent("blue_attenuation_ui", "blue_attenuation", 0.0),
        get_rad("blue_rotation_ui", "blue_rotation", 0.0),
        get_percent("recover_purity_ui", "recover_purity", 0.0),
        int(base_prim),
    )

    packed = pack_sigmoid_params(raw_values)
    return packed.hex()


def apply_sigmoid(
    xmp_path: Path,
    updates: Dict[str, Any],
    requested_num: Optional[int] = None,
    simulate: bool = True,
    limits: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Safely modifies sigmoid parameters in the XMP file.
    """
    content = read_xmp(xmp_path)
    modules = find_operation_modules(content, "sigmoid")
    if not modules:
        return False, "No se encontró el módulo sigmoid en el XMP.", {}

    target = select_target_module(modules, requested_num)
    current_params = decode_sigmoid_hex(target["params"])

    # Merge current params with updates
    merged = {
        "contrast": updates.get("contrast", current_params["contrast"]),
        "skew": updates.get("skew", current_params["skew"]),
        "target_white": updates.get("target_white", current_params["target_white"]),
        "target_black": updates.get("target_black", current_params["target_black"]),
        "color_processing": updates.get("color_processing", current_params["color_processing"]),
        "preserve_hue": updates.get("preserve_hue", current_params["preserve_hue"]),
        "red_attenuation": updates.get("red_attenuation", current_params["raw_tuple"][6]),
        "red_rotation": updates.get("red_rotation", current_params["raw_tuple"][7]),
        "green_attenuation": updates.get("green_attenuation", current_params["raw_tuple"][8]),
        "green_rotation": updates.get("green_rotation", current_params["raw_tuple"][9]),
        "blue_attenuation": updates.get("blue_attenuation", current_params["raw_tuple"][10]),
        "blue_rotation": updates.get("blue_rotation", current_params["raw_tuple"][11]),
        "recover_purity": updates.get("recover_purity", current_params["raw_tuple"][12]),
        "base_primaries": updates.get("base_primaries", current_params["base_primaries"]),
    }

    # Validate safety limits
    if limits:
        c_min, c_max = limits.get("sigmoid_contrast", (0.5, 4.5))
        s_min, s_max = limits.get("sigmoid_skew", (-0.8, 0.8))
        merged["contrast"] = max(c_min, min(c_max, float(merged["contrast"])))
        merged["skew"] = max(s_min, min(s_max, float(merged["skew"])))

    new_hex = encode_sigmoid(merged)

    if simulate:
        return True, "Simulación exitosa (sin cambios en disco).", merged

    # Backup & Atomic write
    backup_path = create_backup(xmp_path)
    try:
        new_content = replace_module_params(content, target, new_hex)
        atomic_write(xmp_path, new_content)

        # Verification
        re_read = read_xmp(xmp_path)
        re_modules = find_operation_modules(re_read, "sigmoid")
        re_target = select_target_module(re_modules, target["num"])
        verified_params = decode_sigmoid_hex(re_target["params"])

        if abs(verified_params["contrast"] - merged["contrast"]) > 0.001 or \
           abs(verified_params["skew"] - merged["skew"]) > 0.001:
            raise RuntimeError("Verificación fallida: discrepancia en los valores escritos.")

        return True, f"Parámetros actualizados exitosamente (num={target['num']}). Backup: {backup_path.name}", merged

    except Exception as e:
        restore_backup(backup_path, xmp_path)
        return False, f"Error durante la escritura. Rollback aplicado: {e}", {}
