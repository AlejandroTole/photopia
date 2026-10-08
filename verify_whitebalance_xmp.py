"""
PHOTOIA - Verify White Balance XMP Roundtrip Test
"""
from pathlib import Path
import sys
from apply.writers.whitebalance import apply_temperature, decode_temperature_hex
from apply.xmp import read_xmp, find_operation_modules, select_target_module


def main():
    print("=" * 70)
    print("PHOTOIA - WHITE BALANCE XMP ROUNDTRIP TEST")
    print("=" * 70)

    xmp_path = Path("_DSC2125.NEF.xmp")
    if not xmp_path.exists():
        print(f"ERROR: No se encontró {xmp_path}")
        return 1

    content = read_xmp(xmp_path)
    mods = find_operation_modules(content, "temperature")
    target = select_target_module(mods, None)
    initial_params = decode_temperature_hex(target["params"])
    print(f"WB inicial (num={target['num']}): red={initial_params['red']}, blue={initial_params['blue']}")

    updates = {"warmth_shift": 0.05}
    success, msg, merged = apply_temperature(xmp_path, updates, target["num"], simulate=True)
    print(f"Simulación: {msg} | Merged: {merged}")

    success, msg, result = apply_temperature(xmp_path, updates, target["num"], simulate=False)
    print(f"Escritura real: {msg}")

    re_content = read_xmp(xmp_path)
    re_mods = find_operation_modules(re_content, "temperature")
    re_target = select_target_module(re_mods, target["num"])
    final_params = decode_temperature_hex(re_target["params"])
    print(f"WB final leído: red={final_params['red']}, blue={final_params['blue']}")

    if abs(final_params["red"] - merged["red"]) < 0.001 and abs(final_params["blue"] - merged["blue"]) < 0.001:
        print("RESULTADO: OK - Roundtrip de white balance verificado con éxito.")
        return 0
    else:
        print("RESULTADO: FALLÓ - Discrepancia en WB.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
