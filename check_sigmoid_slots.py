import argparse
import struct
import sys
from pathlib import Path

from apply.writers.sigmoid import SLOT_BASE_PRIMARIES, SLOT_COLOR_PROCESSING
from apply.xmp import find_operation_modules, read_xmp, select_target_module

SIGMOID_BYTES_LEN = 56
COLOR_PROCESSING_VALUES = range(2)
BASE_PRIMARIES_VALUES = range(5)


def verify_slots(xmp_path: Path, requested_num=None) -> int:
    content = read_xmp(xmp_path)
    modules = find_operation_modules(content, "sigmoid")
    target = select_target_module(modules, requested_num)
    raw = bytes.fromhex(target["params"])
    if len(raw) != SIGMOID_BYTES_LEN:
        raise ValueError(
            f"El módulo sigmoid num={target['num']} tiene {len(raw)} bytes; "
            f"se esperaban {SIGMOID_BYTES_LEN}."
        )

    decoded = {}
    for index in (SLOT_COLOR_PROCESSING, SLOT_BASE_PRIMARIES):
        slot = raw[index * 4:index * 4 + 4]
        decoded[index] = (
            slot.hex(),
            struct.unpack("<i", slot)[0],
            struct.unpack("<f", slot)[0],
        )

    color_bytes, color_int, color_float = decoded[SLOT_COLOR_PROCESSING]
    primaries_bytes, primaries_int, primaries_float = decoded[SLOT_BASE_PRIMARIES]
    print(f"XMP: {xmp_path}")
    print(f"Sigmoid darktable:num={target['num']}")
    print(f"slot 4 bytes={color_bytes}: int32={color_int}, float32={color_float:.9g}")
    print(f"slot 13 bytes={primaries_bytes}: int32={primaries_int}, float32={primaries_float:.9g}")

    if color_int == 0 or primaries_int == 0:
        print(
            "INCONCLUSO: ambos slots deben tener valores no-cero para distinguir "
            "int32 de float32. En darktable selecciona RGB ratio y Rec2020 en "
            "el módulo sigmoid, guarda el XMP y vuelve a ejecutar este script."
        )
        return 2

    if color_int not in COLOR_PROCESSING_VALUES or primaries_int not in BASE_PRIMARIES_VALUES:
        print("FALLO: los valores int32 no coinciden con los enums conocidos de sigmoid.")
        return 1

    if abs(color_float) >= 0.01 or abs(primaries_float) >= 0.01:
        print("INCONCLUSO: la interpretación float32 no es discriminante.")
        return 2

    print("OK: slots 4 y 13 son int32; como float32 se leen como valores subnormales.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verifica los tipos de los slots 4 y 13 del módulo sigmoid."
    )
    parser.add_argument(
        "xmp",
        nargs="?",
        default="_DSC2125.NEF.xmp",
        type=Path,
        help="XMP real guardado por darktable.",
    )
    parser.add_argument("--num", type=int, help="darktable:num del módulo sigmoid.")
    args = parser.parse_args()

    try:
        return verify_slots(args.xmp, args.num)
    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
