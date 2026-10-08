"""
PHOTOIA - Verify Exposure XMP Roundtrip Test
"""
from pathlib import Path
import sys
from apply.writers.exposure import apply_exposure, decode_exposure_hex
from apply.xmp import read_xmp, find_operation_modules, select_target_module


def main():
    print("=" * 70)
    print("PHOTOIA - EXPOSURE XMP ROUNDTRIP TEST")
    print("=" * 70)

    xmp_path = Path("_DSC2125.NEF.xmp")
    if not xmp_path.exists():
        print(f"ERROR: No se encontró {xmp_path}")
        return 1

    content = read_xmp(xmp_path)
    mods = find_operation_modules(content, "exposure")
    target = select_target_module(mods, None)
    initial_params = decode_exposure_hex(target["params"])
    print(f"Exposición inicial (num={target['num']}): {initial_params['exposure']} EV")

    updates = {"exposure": 0.45}
    success, msg, merged = apply_exposure(xmp_path, updates, target["num"], simulate=True)
    print(f"Simulación: {msg} | Merged: {merged}")

    success, msg, result = apply_exposure(xmp_path, updates, target["num"], simulate=False)
    print(f"Escritura real: {msg}")

    re_content = read_xmp(xmp_path)
    re_mods = find_operation_modules(re_content, "exposure")
    re_target = select_target_module(re_mods, target["num"])
    final_params = decode_exposure_hex(re_target["params"])
    print(f"Exposición final leída: {final_params['exposure']} EV")

    if abs(final_params["exposure"] - 0.45) < 0.001:
        print("RESULTADO: OK - Roundtrip de exposure verificado con éxito.")
        return 0
    else:
        print("RESULTADO: FALLÓ - Discrepancia en exposure.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
