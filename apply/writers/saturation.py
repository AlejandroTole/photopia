"""
PHOTOIA - Vibrance/Saturation Writer (v1)
Safe writer for darktable:operation="colorbalancergb" (modversion 5).

Solo expone "vibrance" (viveza inteligente estilo Lightroom, protege pieles y
tonos ya saturados) y "saturation_global" (saturación plana, más agresiva);
el resto de los controles del módulo (tonos partidos por zona, ruedas de
matiz, brillo, contraste y punto gris) se deja en sus valores reales de
fábrica de darktable para que el módulo actúe como un control puro de
punch de color, igual que el "Auto" de Lightroom.

Struct: dt_iop_colorbalancergb_params_t (darktable 5.6.1,
src/iop/colorbalancergb.c, DT_MODULE_INTROSPECTION(5, ...)): 32 campos
float32 seguidos de un enum int32 (saturation_formula). Todos los campos
están empaquetados sin padding (alineación de 4 bytes).
"""
from pathlib import Path
import argparse
import struct
import sys
from typing import Any, Dict, Optional, Tuple

from apply.xmp import (
    read_xmp,
    find_operation_modules,
    select_target_module,
    replace_module_params,
    create_backup,
    restore_backup,
    atomic_write,
)
from config import load_config

COLORBALANCE_OPERATION = "colorbalancergb"
COLORBALANCE_STRUCT_FORMAT = "<32fi"
COLORBALANCE_BYTES_LEN = 132

PARAM_NAMES = [
    "shadows_Y", "shadows_C", "shadows_H",
    "midtones_Y", "midtones_C", "midtones_H",
    "highlights_Y", "highlights_C", "highlights_H",
    "global_Y", "global_C", "global_H",
    "shadows_weight", "white_fulcrum", "highlights_weight",
    "chroma_shadows", "chroma_highlights", "chroma_global", "chroma_midtones",
    "saturation_global", "saturation_highlights", "saturation_midtones", "saturation_shadows",
    "hue_angle",
    "brilliance_global", "brilliance_highlights", "brilliance_midtones", "brilliance_shadows",
    "mask_grey_fulcrum",
    "vibrance",
    "grey_fulcrum",
    "contrast",
    "saturation_formula",  # int32 enum: 0=JzAzBz (2021), 1=darktable UCS (2022)
]


def decode_colorbalance_hex(hex_data: str) -> Dict[str, Any]:
    raw = bytes.fromhex(hex_data)
    if len(raw) != COLORBALANCE_BYTES_LEN:
        raise ValueError(
            f"Se esperaban {COLORBALANCE_BYTES_LEN} bytes para colorbalancergb, "
            f"recibidos {len(raw)}"
        )
    values = struct.unpack(COLORBALANCE_STRUCT_FORMAT, raw)
    return dict(zip(PARAM_NAMES, values))


def encode_colorbalance(params: Dict[str, Any]) -> str:
    ordered = [
        int(params[name]) if name == "saturation_formula" else float(params[name])
        for name in PARAM_NAMES
    ]
    packed = struct.pack(COLORBALANCE_STRUCT_FORMAT, *ordered)
    if len(packed) != COLORBALANCE_BYTES_LEN:
        raise RuntimeError(
            f"colorbalancergb debe ocupar exactamente {COLORBALANCE_BYTES_LEN} bytes."
        )
    return packed.hex()


def apply_vibrance(
    xmp_path: Path,
    updates: Dict[str, Any],
    requested_num: Optional[int] = None,
    simulate: bool = True,
    limits: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Safely modifies vibrance/saturation parameters in the XMP file.
    """
    content = read_xmp(xmp_path)
    modules = find_operation_modules(content, COLORBALANCE_OPERATION)
    if not modules:
        return False, "No se encontró el módulo colorbalancergb en el XMP.", {}

    target = select_target_module(modules, requested_num)
    current_params = decode_colorbalance_hex(target["params"])

    vibrance_val = float(updates.get("vibrance", current_params["vibrance"]))
    saturation_val = float(
        updates.get("saturation_global", current_params["saturation_global"])
    )

    if limits:
        v_min, v_max = limits.get("saturation_vibrance", (-0.3, 0.5))
        vibrance_val = max(v_min, min(v_max, vibrance_val))

        s_min, s_max = limits.get("saturation_global", (-0.2, 0.3))
        saturation_val = max(s_min, min(s_max, saturation_val))

    merged = {
        **current_params,
        "vibrance": vibrance_val,
        "saturation_global": saturation_val,
    }

    new_hex = encode_colorbalance(merged)

    if simulate:
        return True, "Simulación exitosa (sin cambios en disco).", merged

    backup_path = create_backup(xmp_path)
    try:
        new_content = replace_module_params(content, target, new_hex)

        # Verify that only target module changed
        orig_modules = find_operation_modules(content, COLORBALANCE_OPERATION)
        new_modules = find_operation_modules(new_content, COLORBALANCE_OPERATION)
        if len(orig_modules) != len(new_modules):
            raise RuntimeError("El número de módulos colorbalancergb cambió.")

        atomic_write(xmp_path, new_content)

        # Verification post-write
        re_read = read_xmp(xmp_path)
        re_modules = find_operation_modules(re_read, COLORBALANCE_OPERATION)
        re_target = select_target_module(re_modules, target["num"])
        verified_params = decode_colorbalance_hex(re_target["params"])

        if (
            abs(verified_params["vibrance"] - merged["vibrance"]) > 0.001
            or abs(verified_params["saturation_global"] - merged["saturation_global"]) > 0.001
        ):
            raise RuntimeError("Verificación fallida: discrepancia en vibrance/saturación.")

        return (
            True,
            f"Vibrance/saturación actualizada exitosamente (num={target['num']}). "
            f"Backup: {backup_path.name}",
            merged,
        )

    except Exception as e:
        restore_backup(backup_path, xmp_path)
        return False, f"Error durante la escritura. Rollback aplicado: {e}", {}


def main() -> int:
    parser = argparse.ArgumentParser(description="PHOTOIA - Vibrance/Saturation Writer")
    parser.add_argument("--xmp", type=str, default="_DSC2125.NEF.xmp", help="Ruta al archivo XMP")
    parser.add_argument("--vibrance", type=float, default=0.15, help="Viveza (vibrance) nueva")
    parser.add_argument(
        "--saturation", type=float, default=0.0, help="Saturación global (saturation_global) nueva"
    )
    parser.add_argument("--num", type=int, default=None, help="Número darktable:num del módulo target")
    parser.add_argument("--write", action="store_true", help="Escribir cambios en disco (por defecto simulación)")
    args = parser.parse_args()

    xmp_path = Path(args.xmp)
    if not xmp_path.exists():
        print(f"ERROR: No se encontró el XMP: {xmp_path}")
        return 1

    config = load_config()
    limits = config.get("limits", {})

    updates = {
        "vibrance": args.vibrance,
        "saturation_global": args.saturation,
    }

    print("=" * 60)
    print("PHOTOIA - VIBRANCE/SATURATION WRITER")
    print("=" * 60)
    print(f"XMP: {xmp_path}")
    print(f"Modo: {'ESCRITURA REAL' if args.write else 'SIMULACION'}")
    print(f"Actualizaciones solicitadas: {updates}")
    print()

    success, message, result = apply_vibrance(
        xmp_path=xmp_path,
        updates=updates,
        requested_num=args.num,
        simulate=not args.write,
        limits=limits,
    )

    if not success:
        print(f"ERROR: {message}")
        return 1

    print(f"ESTADO: OK")
    print(f"MENSAJE: {message}")
    print(f"RESULTADO: vibrance={result['vibrance']:.3f}, saturation_global={result['saturation_global']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
