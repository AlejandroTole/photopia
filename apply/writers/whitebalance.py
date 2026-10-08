"""
PHOTOIA - White Balance Writer (v2)
Safe writer for darktable:operation="temperature" (modversion 4).
Struct format: <ffffi (20 bytes).
"""
from pathlib import Path
import struct
import argparse
import sys
from typing import Dict, Any, Tuple, Optional

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

TEMPERATURE_STRUCT_FORMAT = "<ffffi"
TEMPERATURE_BYTES_LEN = 20


def decode_temperature_hex(hex_data: str) -> Dict[str, Any]:
    raw = bytes.fromhex(hex_data)
    if len(raw) != TEMPERATURE_BYTES_LEN:
        raise ValueError(f"Se esperaban {TEMPERATURE_BYTES_LEN} bytes para temperature, recibidos {len(raw)}")

    red, green, blue, various, preset = struct.unpack(TEMPERATURE_STRUCT_FORMAT, raw)

    return {
        "red": red,
        "green": green,
        "blue": blue,
        "various": various,
        "preset": preset,
    }


def encode_temperature(params: Dict[str, Any]) -> str:
    raw_values = (
        float(params.get("red", 2.0)),
        float(params.get("green", 1.0)),
        float(params.get("blue", 1.5)),
        float(params.get("various", 0.0)),
        int(params.get("preset", 4)),
    )
    packed = struct.pack(TEMPERATURE_STRUCT_FORMAT, *raw_values)
    return packed.hex()


def apply_temperature(
    xmp_path: Path,
    updates: Dict[str, Any],
    requested_num: Optional[int] = None,
    simulate: bool = True,
    limits: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Safely modifies white balance / temperature coefficients in XMP.
    """
    content = read_xmp(xmp_path)
    modules = find_operation_modules(content, "temperature")
    if not modules:
        return False, "No se encontró el módulo temperature en el XMP.", {}

    target = select_target_module(modules, requested_num)
    current_params = decode_temperature_hex(target["params"])

    red_val = current_params["red"]
    blue_val = current_params["blue"]

    warmth_shift = float(updates.get("warmth_shift", 0.0))
    if warmth_shift != 0.0:
        min_ratio, max_ratio = (-0.15, 0.15)
        if limits and "temperature_delta_ratio" in limits:
            min_ratio, max_ratio = limits["temperature_delta_ratio"]
        warmth_shift = max(min_ratio, min(max_ratio, warmth_shift))

        red_val *= (1.0 + warmth_shift)
        blue_val *= (1.0 - warmth_shift)

    if "red" in updates:
        red_val = float(updates["red"])
    if "blue" in updates:
        blue_val = float(updates["blue"])

    red_val = max(0.5, min(4.0, red_val))
    blue_val = max(0.5, min(4.0, blue_val))

    merged = {
        **current_params,
        "red": red_val,
        "blue": blue_val,
    }

    new_hex = encode_temperature(merged)

    if simulate:
        return True, "Simulación exitosa (sin cambios en disco).", merged

    backup_path = create_backup(xmp_path)
    try:
        new_content = replace_module_params(content, target, new_hex)

        orig_modules = find_operation_modules(content, "temperature")
        new_modules = find_operation_modules(new_content, "temperature")
        if len(orig_modules) != len(new_modules):
            raise RuntimeError("El número de módulos temperature cambió.")

        atomic_write(xmp_path, new_content)

        re_read = read_xmp(xmp_path)
        re_modules = find_operation_modules(re_read, "temperature")
        re_target = select_target_module(re_modules, target["num"])
        verified_params = decode_temperature_hex(re_target["params"])

        if abs(verified_params["red"] - merged["red"]) > 0.001 or \
           abs(verified_params["blue"] - merged["blue"]) > 0.001:
            raise RuntimeError("Verificación fallida: discrepancia en los coeficientes WB.")

        return True, f"Temperature actualizado exitosamente (num={target['num']}). Backup: {backup_path.name}", merged

    except Exception as e:
        restore_backup(backup_path, xmp_path)
        return False, f"Error durante la escritura. Rollback aplicado: {e}", {}


def main() -> int:
    parser = argparse.ArgumentParser(description="PHOTOIA - White Balance Writer")
    parser.add_argument("--xmp", type=str, default="_DSC2125.NEF.xmp", help="Ruta al archivo XMP")
    parser.add_argument("--warmth-shift", type=float, default=0.05, help="Cambio de calidez relactiva (warmth_shift)")
    parser.add_argument("--red", type=float, default=None, help="Multiplicador rojo directo")
    parser.add_argument("--blue", type=float, default=None, help="Multiplicador azul directo")
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
        "warmth_shift": args.warmth_shift,
    }
    if args.red is not None:
        updates["red"] = args.red
    if args.blue is not None:
        updates["blue"] = args.blue

    print("=" * 60)
    print("PHOTOIA - WHITE BALANCE WRITER")
    print("=" * 60)
    print(f"XMP: {xmp_path}")
    print(f"Modo: {'ESCRITURA REAL' if args.write else 'SIMULACION'}")
    print(f"Actualizaciones solicitadas: {updates}")
    print()

    success, message, result = apply_temperature(
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
    print(f"RESULTADO: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
