import re
import math
from apply.writers.sigmoid import (
    SLOT_BASE_PRIMARIES,
    SLOT_COLOR_PROCESSING,
    unpack_sigmoid_params,
)


TEST_XMP = "_DSC2125.TEST.NEF.xmp"


PARAM_NAMES = [
    "middle_grey_contrast",
    "contrast_skewness",
    "display_white_target",
    "display_black_target",
    "color_processing",
    "hue_preservation",
    "red_inset",
    "red_rotation",
    "green_inset",
    "green_rotation",
    "blue_inset",
    "blue_rotation",
    "purity",
    "base_primaries",
]


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


def extract_latest_sigmoid(xmp):

    pattern = re.compile(
        r'<rdf:li\b'
        r'(?P<attrs>[^>]*)'
        r'darktable:operation="sigmoid"'
        r'(?P<attrs2>[^>]*)'
        r'darktable:params="(?P<params>[0-9a-fA-F]+)"'
        r'[^>]*>',
        re.S,
    )

    matches = []

    for match in pattern.finditer(xmp):

        attrs = (
            match.group("attrs")
            + match.group("attrs2")
        )

        num_match = re.search(
            r'darktable:num="(\d+)"',
            attrs,
        )

        enabled_match = re.search(
            r'darktable:enabled="(\d+)"',
            attrs,
        )

        num = (
            int(num_match.group(1))
            if num_match
            else -1
        )

        enabled = (
            int(enabled_match.group(1))
            if enabled_match
            else None
        )

        matches.append(
            {
                "num": num,
                "enabled": enabled,
                "params": match.group("params"),
            }
        )

    if not matches:
        raise RuntimeError(
            "No se encontró ningún Sigmoid."
        )

    matches.sort(
        key=lambda item: item["num"]
    )

    return matches[-1]


def unpack_params(hex_data):

    raw = bytes.fromhex(hex_data)

    if len(raw) != 56:
        raise RuntimeError(
            f"Sigmoid inválido: {len(raw)} bytes."
        )

    return unpack_sigmoid_params(raw)


def print_value(index, value):

    if index == SLOT_COLOR_PROCESSING:

        print(
            f"[{index:2}] "
            f"{PARAM_NAMES[index]:<24} "
            f"{value:d}  "
            f"({COLOR_PROCESSING.get(
                int(round(value)),
                'UNKNOWN'
            )})"
        )

    elif index == 5:

        print(
            f"[{index:2}] "
            f"{PARAM_NAMES[index]:<24} "
            f"{value:.9f}"
        )

    elif index in (6, 8, 10, 12):

        print(
            f"[{index:2}] "
            f"{PARAM_NAMES[index]:<24} "
            f"{value:.12f}  "
            f"({value * 100:.6f}%)"
        )

    elif index in (7, 9, 11):

        print(
            f"[{index:2}] "
            f"{PARAM_NAMES[index]:<24} "
            f"{value:.12f}  "
            f"({math.degrees(value):.6f}°)"
        )

    elif index == SLOT_BASE_PRIMARIES:

        print(
            f"[{index:2}] "
            f"{PARAM_NAMES[index]:<24} "
            f"{value:d}  "
            f"({BASE_PRIMARIES.get(
                int(round(value)),
                'UNKNOWN'
            )})"
        )

    else:

        print(
            f"[{index:2}] "
            f"{PARAM_NAMES[index]:<24} "
            f"{value:.12f}"
        )


def main():

    print()
    print("=" * 78)
    print("PHOTOIA - VERIFY TEST XMP")
    print("=" * 78)

    try:

        with open(
            TEST_XMP,
            "r",
            encoding="utf-8"
        ) as f:

            xmp = f.read()

    except FileNotFoundError:

        print()
        print("ERROR: No existe:")
        print(TEST_XMP)
        print()

        return 1

    sigmoid = extract_latest_sigmoid(
        xmp
    )

    values = unpack_params(
        sigmoid["params"]
    )

    print()
    print(
        f"Sigmoid: darktable:num="
        f"{sigmoid['num']}"
    )

    print(
        f"Enabled: {sigmoid['enabled']}"
    )

    print()
    print("14 PARAMETROS LEIDOS")
    print("-" * 78)

    for i, value in enumerate(values):

        print_value(
            i,
            value
        )

    print()
    print("=" * 78)
    print("VERIFICACION DE LOS VALORES ESPERADOS")
    print("=" * 78)

    expected = [
        3.0,
        -0.33,
        71.61,
        0.2677,
        0,
        70.53,
        0.104,
        math.radians(11.8),
        0.102,
        math.radians(10.0),
        0.102,
        math.radians(19.5),
        0.36,
        0,
    ]

    all_ok = True

    for i in range(14):

        difference = (
            values[i] - expected[i]
        )

        # Tolerancia suficientemente pequeña
        # para float32 y conversiones angulares.
        if abs(difference) > 0.00001:

            all_ok = False

            print(
                f"ERROR [{i}] "
                f"{PARAM_NAMES[i]} "
                f"diferencia={difference:.12f}"
            )

    print()

    if all_ok:

        print("RESULTADO: OK")
        print()
        print(
            "El XMP de prueba contiene exactamente "
            "los parametros esperados dentro de "
            "la tolerancia establecida."
        )

    else:

        print("RESULTADO: REVISAR")

    print()
    print("=" * 78)
    print("FIN")
    print("=" * 78)
    print()

    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())