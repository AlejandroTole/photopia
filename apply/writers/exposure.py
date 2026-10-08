"""
PHOTOIA - Exposure Writer (v2)
Safe writer for darktable:operation="exposure" (modversion 7).
Struct format: <iffffii (28 bytes).
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

EXPOSURE_STRUCT_FORMAT = "<iffffii"
EXPOSURE_BYTES_LEN = 28


def decode_exposure_hex(hex_data: str) -> Dict[str, Any]:
    raw = bytes.fromhex(hex_data)
    if len(raw) != EXPOSURE_BYTES_LEN:
        raise ValueError(f"Se esperaban {EXPOSURE_BYTES_LEN} bytes para exposure, recibidos {len(raw)}")

    mode, black, exposure, deflicker_p, deflicker_target, comp_bias, comp_hilite = struct.unpack(
        EXPOSURE_STRUCT_FORMAT, raw
    )

    return {
        "mode": mode,
        "black": black,
        "exposure": exposure,  # EV correction
        "deflicker_percentile": deflicker_p,
        "deflicker_target_level": deflicker_target,
        "compensate_exposure_bias": comp_bias,
        "compensate_hilite_pres": comp_hilite,
    }


def encode_exposure(params: Dict[str, Any]) -> str:
    raw_values = (
        int(params.get("mode", 0)),
        float(params.get("black", 0.0)),
        float(params.get("exposure", 0.0)),
        float(params.get("deflicker_percentile", 50.0)),
        float(params.get("deflicker_target_level", -4.0)),
        int(params.get("compensate_exposure_bias", 1)),
        int(params.get("compensate_hilite_pres", 1)),
    )
    packed = struct.pack(EXPOSURE_STRUCT_FORMAT, *raw_values)
    return packed.hex()


def apply_exposure(
    xmp_path: Path,
    updates: Dict[str, Any],
    requested_num: Optional[int] = None,
    simulate: bool = True,
    limits: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Safely modifies exposure parameters in the XMP file.
    """
    content = read_xmp(xmp_path)
    modules = find_operation_modules(content, "exposure")
    if not modules:
        return False, "No se encontró el módulo exposure en el XMP.", {}

    target = select_target_module(modules, requested_num)
    current_params = decode_exposure_hex(target["params"])

    ev_val = float(updates.get("exposure", updates.get("ev", current_params["exposure"])))
    black_val = float(updates.get("black", current_params["black"]))

    if limits:
        ev_min, ev_max = limits.get("exposure_ev", (-1.0, 1.0))
        ev_val = max(ev_min, min(ev_max, ev_val))

        b_min, b_max = limits.get("exposure_black", (-0.05, 0.05))
        black_val = max(b_min, min(b_max, black_val))

    merged = {
        **current_params,
        "exposure": ev_val,
        "black": black_val,
    }

    new_hex = encode_exposure(merged)

    if simulate:
        return True, "Simulación exitosa (sin cambios en disco).", merged

    backup_path = create_backup(xmp_path)
    try:
        new_content = replace_module_params(content, target, new_hex)

        # Verify that only target module changed
        orig_modules = find_operation_modules(content, "exposure")
        new_modules = find_operation_modules(new_content, "exposure")
        if len(orig_modules) != len(new_modules):
            raise RuntimeError("El número de módulos exposure cambió.")

        atomic_write(xmp_path, new_content)

        # Verification post-write
        re_read = read_xmp(xmp_path)
        re_modules = find_operation_modules(re_read, "exposure")
        re_target = select_target_module(re_modules, target["num"])
        verified_params = decode_exposure_hex(re_target["params"])

        if abs(verified_params["exposure"] - merged["exposure"]) > 0.001:
            raise RuntimeError("Verificación fallida: discrepancia en el valor de exposición.")

        return True, f"Exposure actualizado exitosamente (num={target['num']}). Backup: {backup_path.name}", merged

    except Exception as e:
        restore_backup(backup_path, xmp_path)
        return False, f"Error durante la escritura. Rollback aplicado: {e}", {}


def main() -> int:
    parser = argparse.ArgumentParser(description="PHOTOIA - Exposure Writer")
    parser.add_argument("--xmp", type=str, default="_DSC2125.NEF.xmp", help="Ruta al archivo XMP")
    parser.add_argument("--exposure", type=float, default=0.5, help="Nuevo valor de exposición (EV)")
    parser.add_argument("--black", type=float, default=0.0, help="Nuevo valor de nivel de negros")
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
        "exposure": args.exposure,
        "black": args.black,
    }

    print("=" * 60)
    print("PHOTOIA - EXPOSURE WRITER")
    print("=" * 60)
    print(f"XMP: {xmp_path}")
    print(f"Modo: {'ESCRITURA REAL' if args.write else 'SIMULACION'}")
    print(f"Actualizaciones solicitadas: {updates}")
    print()

    success, message, result = apply_exposure(
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
